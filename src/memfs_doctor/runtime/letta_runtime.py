from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import tty
from typing import Any

from memfs_doctor.core.events import EventKind, MemoryEvent, utc_now_iso


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
PROMPT_RE = re.compile(r"[›>]\s+(.*\S)\s*$")
QUESTION_PREFIXES = (
    "what ",
    "where ",
    "when ",
    "who ",
    "which ",
    "how ",
    "do ",
    "does ",
    "did ",
    "is ",
    "are ",
    "can ",
    "could ",
    "would ",
    "will ",
)
MISS_PATTERNS = (
    "i don't know",
    "i do not know",
    "don't know that one",
    "don't have that information",
    "i don't have that information",
    "want to tell me",
)
STATUS_ONLY_PREFIXES = (
    "letta code is remembering",
    "resuming conversation with letta code",
)
STATUS_LINE_PREFIXES = STATUS_ONLY_PREFIXES + (
    "└  tip:",
    "tip:",
    "press / for commands",
    "press ctrl-c again to exit",
)


@dataclass(slots=True)
class RecordedLine:
    timestamp: str
    text: str


@dataclass(slots=True)
class TranscriptTurn:
    query: str
    query_timestamp: str
    response_timestamp: str | None = None
    response_lines: list[str] = field(default_factory=list)
    memory_lines: list[str] = field(default_factory=list)


def default_runtime_trace_path(workspace_root: Path, capture_id: str) -> Path:
    return workspace_root / ".memfs_doctor" / "runtime" / f"{capture_id}.jsonl"


def default_transcript_path(workspace_root: Path, capture_id: str) -> Path:
    return workspace_root / ".memfs_doctor" / "transcripts" / f"{capture_id}.log"


def sanitize_terminal_line(text: str) -> str:
    return ANSI_RE.sub("", text).replace("\r", "").strip("\n")


def is_question(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized.endswith("?") or normalized.startswith(QUESTION_PREFIXES)


def parse_transcript_turns(lines: list[RecordedLine]) -> list[TranscriptTurn]:
    turns: list[TranscriptTurn] = []
    current: TranscriptTurn | None = None
    pending_query: tuple[str, str] | None = None

    for recorded in lines:
        raw = sanitize_terminal_line(recorded.text).strip()
        if not raw:
            continue
        prompt_match = PROMPT_RE.search(raw)
        if prompt_match:
            prompt_text = prompt_match.group(1).strip()
            if prompt_text:
                if current is not None:
                    current = None
                pending_query = (prompt_text, recorded.timestamp)
            continue
        if raw.startswith(("✻ Thinking", "* Thinking")):
            if current is None and pending_query is not None:
                current = TranscriptTurn(query=pending_query[0], query_timestamp=pending_query[1])
                turns.append(current)
                pending_query = None
            continue
        if raw.startswith(("• memory ", "memory ")):
            if current is None and pending_query is not None:
                current = TranscriptTurn(query=pending_query[0], query_timestamp=pending_query[1])
                turns.append(current)
                pending_query = None
            if current is None:
                continue
            if current.response_timestamp is None:
                current.response_timestamp = recorded.timestamp
            current.memory_lines.append(raw.replace("• ", "", 1))
            continue
        if raw.startswith("• "):
            if current is None and pending_query is not None:
                current = TranscriptTurn(query=pending_query[0], query_timestamp=pending_query[1])
                turns.append(current)
                pending_query = None
            if current is None:
                continue
            if current.response_timestamp is None:
                current.response_timestamp = recorded.timestamp
            current.response_lines.append(raw[2:].strip())
            continue
        if current is None:
            continue
        if current.response_lines:
            current.response_lines.append(raw)
        elif current.memory_lines:
            current.memory_lines.append(raw)

    return turns


def infer_runtime_events_from_turns(
    turns: list[TranscriptTurn],
    *,
    agent_id: str,
    session_id: str,
    source: str = "letta-runtime-recorder",
) -> list[MemoryEvent]:
    events: list[MemoryEvent] = []
    ordinal = 0
    for turn in turns:
        if not is_question(turn.query):
            continue
        filtered_response_lines = [line for line in turn.response_lines if not is_status_response_line(line)]
        response_text = "\n".join(filtered_response_lines).strip()
        if not response_text or is_status_only_response(response_text):
            continue
        miss = any(pattern in response_text.lower() for pattern in MISS_PATTERNS)
        kind = EventKind.MEMORY_RETRIEVAL_MISS if miss else EventKind.MEMORY_RETRIEVED
        latency_ms = None
        if turn.response_timestamp is not None:
            started = datetime.fromisoformat(turn.query_timestamp)
            ended = datetime.fromisoformat(turn.response_timestamp)
            latency_ms = round((ended - started).total_seconds() * 1000, 2)
        ordinal += 1
        events.append(
            MemoryEvent(
                event_id=f"{session_id}:recorder:{ordinal}",
                kind=kind,
                framework="letta",
                agent_id=agent_id,
                session_id=session_id,
                timestamp=turn.response_timestamp or turn.query_timestamp,
                source=source,
                query=turn.query,
                metadata={
                    "inferred": True,
                    "response_text": response_text,
                    "memory_lines": list(turn.memory_lines),
                },
                latency_ms=latency_ms,
            )
        )
    return events


def is_status_only_response(text: str) -> bool:
    normalized = text.strip().lower()
    return any(normalized.startswith(prefix) for prefix in STATUS_ONLY_PREFIXES)


def is_status_response_line(text: str) -> bool:
    normalized = text.strip().lower()
    return any(normalized.startswith(prefix) for prefix in STATUS_LINE_PREFIXES)


def write_runtime_trace(path: str | Path, events: list[MemoryEvent]) -> Path:
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text("\n".join(event.to_json() for event in events) + ("\n" if events else ""), encoding="utf-8")
    return trace_path


class InteractiveRuntimeRecorder:
    def __init__(self) -> None:
        self._buffer = ""
        self._stdin_buffer = ""
        self.lines: list[RecordedLine] = []

    def run(self, command: list[str]) -> tuple[int, list[RecordedLine]]:
        if not command:
            raise ValueError("Command is required.")
        executable = command[0]
        if not shutil.which(executable) and not Path(executable).exists():
            raise FileNotFoundError(f"Command not found: {executable}")
        return self._run_with_pty(command)

    def _run_with_pty(self, command: list[str]) -> tuple[int, list[RecordedLine]]:
        master_fd, slave_fd = pty.openpty()
        self._apply_terminal_size(slave_fd)

        process = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)

        stdin_fd = sys.stdin.fileno()
        stdin_is_tty = os.isatty(stdin_fd)
        stdin_available = True
        original_tty_attrs = termios.tcgetattr(stdin_fd) if stdin_is_tty else None

        def handle_winch(signum: int, frame: Any) -> None:
            del signum, frame
            self._apply_terminal_size(master_fd)

        previous_winch = signal.getsignal(signal.SIGWINCH)

        try:
            if stdin_is_tty:
                tty.setraw(stdin_fd)
            signal.signal(signal.SIGWINCH, handle_winch)
            self._apply_terminal_size(master_fd)

            while True:
                read_fds = [master_fd]
                if stdin_available:
                    read_fds.append(stdin_fd)
                ready, _, _ = select.select(read_fds, [], [])

                if master_fd in ready:
                    try:
                        data = os.read(master_fd, 1024)
                    except OSError:
                        data = b""
                    if data:
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                        self._record_bytes(data)
                    elif process.poll() is not None:
                        break

                if stdin_available and stdin_fd in ready:
                    try:
                        data = os.read(stdin_fd, 1024)
                    except OSError:
                        data = b""
                    if data:
                        self._record_stdin_bytes(data)
                        os.write(master_fd, data)
                    else:
                        stdin_available = False

                if process.poll() is not None and master_fd not in ready:
                    break
        finally:
            if stdin_is_tty and original_tty_attrs is not None:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, original_tty_attrs)
            signal.signal(signal.SIGWINCH, previous_winch)
            self._flush_buffer()
            os.close(master_fd)

        return process.wait(), self.lines

    def _apply_terminal_size(self, fd: int) -> None:
        columns, lines = shutil.get_terminal_size(fallback=(120, 40))
        winsize = struct.pack("HHHH", lines, columns, 0, 0)
        try:
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except OSError:
            return

    def _record_bytes(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self.lines.append(RecordedLine(timestamp=utc_now_iso(), text=line))

    def _flush_buffer(self) -> None:
        remainder = self._buffer.strip("\n")
        if remainder:
            self.lines.append(RecordedLine(timestamp=utc_now_iso(), text=remainder))
        self._buffer = ""

    def _record_stdin_bytes(self, data: bytes) -> None:
        for byte in data:
            if byte in {10, 13}:
                text = self._stdin_buffer.strip()
                if text:
                    self.lines.append(RecordedLine(timestamp=utc_now_iso(), text=f"> {text}"))
                self._stdin_buffer = ""
                continue
            if byte in {8, 127}:
                self._stdin_buffer = self._stdin_buffer[:-1]
                continue
            if 32 <= byte <= 126:
                self._stdin_buffer += chr(byte)


def write_raw_transcript(path: str | Path, lines: list[RecordedLine]) -> Path:
    transcript_path = Path(path)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        "\n".join(f"{line.timestamp}\t{sanitize_terminal_line(line.text)}" for line in lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )
    return transcript_path


def record_runtime_trace(
    *,
    agent_id: str,
    session_id: str,
    command: list[str],
    output_path: str | Path,
    transcript_path: str | Path,
) -> tuple[int, Path, Path, list[MemoryEvent]]:
    recorder = InteractiveRuntimeRecorder()
    exit_code, lines = recorder.run(command)
    turns = parse_transcript_turns(lines)
    events = infer_runtime_events_from_turns(turns, agent_id=agent_id, session_id=session_id)
    path = write_runtime_trace(output_path, events)
    raw_path = write_raw_transcript(transcript_path, lines)
    return exit_code, path, raw_path, events
