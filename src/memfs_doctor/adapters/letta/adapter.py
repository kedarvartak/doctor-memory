from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any
from uuid import uuid4

from memfs_doctor.adapters.base import AdapterError, BaseAdapter
from memfs_doctor.core.events import EventKind, MemoryEvent, utc_now_iso


LETTA_KIND_MAP = {
    "session_started": EventKind.SESSION_STARTED,
    "session_ended": EventKind.SESSION_ENDED,
    "memory_created": EventKind.MEMORY_CREATED,
    "memory_updated": EventKind.MEMORY_UPDATED,
    "memory_deleted": EventKind.MEMORY_DELETED,
    "memory_retrieved": EventKind.MEMORY_RETRIEVED,
    "memory_retrieval_miss": EventKind.MEMORY_RETRIEVAL_MISS,
    "summary_generated": EventKind.SUMMARY_GENERATED,
    "compaction_run": EventKind.COMPACTION_RUN,
}


class LettaTraceAdapter(BaseAdapter):
    framework = "letta"

    def __init__(self, state: "LettaLocalState | None" = None) -> None:
        self.state = state or LettaLocalState()

    def load_events(self, path: str | Path) -> list[MemoryEvent]:
        trace_path = Path(path)
        if not trace_path.exists():
            raise AdapterError(f"Trace file does not exist: {trace_path}")

        events: list[MemoryEvent] = []
        with trace_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise AdapterError(f"Invalid JSON on line {line_number}: {exc}") from exc
                events.append(self._normalize(payload, line_number))
        return events

    def discover_agents(self) -> list["LettaAgent"]:
        agents_root = self.state.agents_dir
        if not agents_root.exists():
            return []

        discovered: list[LettaAgent] = []
        for entry in sorted(agents_root.iterdir()):
            if not entry.is_dir():
                continue
            memory_dir = entry / "memory"
            if memory_dir.is_dir():
                discovered.append(LettaAgent(agent_id=entry.name, memory_dir=memory_dir))
        return discovered

    def resolve_memory_dir(self, agent_id: str | None = None, memory_dir: str | Path | None = None) -> Path:
        if memory_dir is not None:
            path = Path(memory_dir).expanduser().resolve()
            if not path.exists():
                raise AdapterError(f"Memory directory does not exist: {path}")
            return path
        if not agent_id:
            raise AdapterError("Provide either agent_id or memory_dir.")
        path = self.state.agents_dir / agent_id / "memory"
        if not path.exists():
            raise AdapterError(f"Could not resolve Letta memory directory for agent {agent_id!r}")
        return path

    def load_events_from_agent(self, agent_id: str) -> list[MemoryEvent]:
        return self.load_events_from_memory_repo(self.resolve_memory_dir(agent_id=agent_id))

    def load_events_from_memory_repo(self, memory_dir: str | Path) -> list[MemoryEvent]:
        repo = self.resolve_memory_dir(memory_dir=memory_dir)
        agent_id = self._agent_id_from_memory_dir(repo)
        session_id = f"letta-git:{agent_id}:{self._git_output(repo, ['rev-parse', '--short', 'HEAD']).strip()}"
        return self._build_git_events(repo=repo, agent_id=agent_id, session_id=session_id)

    def start_session_capture(self, agent_id: str | None = None, memory_dir: str | Path | None = None) -> "LettaCapture":
        repo = self.resolve_memory_dir(agent_id=agent_id, memory_dir=memory_dir)
        resolved_agent_id = self._agent_id_from_memory_dir(repo)
        head_sha = self._git_output(repo, ["rev-parse", "HEAD"]).strip()
        session_context = self.state.get_last_session(agent_id=resolved_agent_id)
        capture_id = f"letta-session:{resolved_agent_id}:{session_context.conversation_id}:{uuid4().hex[:12]}"
        capture = LettaCapture(
            capture_id=capture_id,
            agent_id=resolved_agent_id,
            memory_dir=repo,
            base_head=head_sha,
            started_at=utc_now_iso(),
            conversation_id=session_context.conversation_id,
        )
        self.state.save_capture(capture)
        return capture

    def finish_session_capture(self, capture_id: str, runtime_trace_path: str | Path | None = None) -> list[MemoryEvent]:
        capture = self.state.load_capture(capture_id)
        repo = capture.memory_dir
        if not repo.exists():
            raise AdapterError(f"Captured memory directory no longer exists: {repo}")

        ended_at = utc_now_iso()
        events = self._build_git_events(
            repo=repo,
            agent_id=capture.agent_id,
            session_id=capture.capture_id,
            since_head=capture.base_head,
            started_at=capture.started_at,
            ended_at=ended_at,
            metadata={
                "capture_id": capture.capture_id,
                "conversation_id": capture.conversation_id,
                "capture_mode": "incremental",
            },
        )
        if runtime_trace_path is not None:
            runtime_events = self._load_runtime_trace_for_capture(
                path=runtime_trace_path,
                capture=capture,
                ended_at=ended_at,
            )
            events.extend(runtime_events)
            events = sorted(events, key=lambda event: (event.timestamp, event.event_id))
        self.state.delete_capture(capture_id)
        return events

    def list_captures(self) -> list["LettaCapture"]:
        return self.state.list_captures()

    def _build_git_events(
        self,
        repo: Path,
        agent_id: str,
        session_id: str,
        since_head: str | None = None,
        started_at: str | None = None,
        ended_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[MemoryEvent]:
        shared_metadata = dict(metadata or {})

        log_args = ["log", "--reverse", "--format=%H%x1f%aI%x1f%s"]
        if since_head:
            log_args.append(f"{since_head}..HEAD")
        commits_output = self._git_output(repo, log_args)
        commits = [line for line in commits_output.splitlines() if line.strip()]
        if not commits and not since_head:
            raise AdapterError(f"No git history found in memory repository: {repo}")

        events: list[MemoryEvent] = []
        first_timestamp = started_at or (commits[0].split("\x1f")[1] if commits else utc_now_iso())
        last_timestamp = ended_at or (commits[-1].split("\x1f")[1] if commits else first_timestamp)
        events.append(
            MemoryEvent(
                event_id=f"{session_id}:start",
                kind=EventKind.SESSION_STARTED,
                framework=self.framework,
                agent_id=agent_id,
                session_id=session_id,
                timestamp=first_timestamp,
                source="letta-git-import",
                metadata={"memory_dir": str(repo), **shared_metadata},
            )
        )

        ordinal = 0
        for line in commits:
            commit_sha, commit_time, subject = line.split("\x1f", 2)
            changes = self._git_output(
                repo,
                ["diff-tree", "--root", "--no-commit-id", "--name-status", "-r", commit_sha],
            )
            for change_line in changes.splitlines():
                if not change_line.strip():
                    continue
                status, rel_path = change_line.split("\t", 1)
                if not self._is_memory_markdown(rel_path):
                    continue
                ordinal += 1
                memory_id = rel_path
                before = None
                after = None
                kind = EventKind.MEMORY_UPDATED
                if status == "A":
                    kind = EventKind.MEMORY_CREATED
                    after = self._read_markdown_at_commit(repo, commit_sha, rel_path)
                elif status == "M":
                    kind = EventKind.MEMORY_UPDATED
                    after = self._read_markdown_at_commit(repo, commit_sha, rel_path)
                    parent = self._first_parent(repo, commit_sha)
                    before = self._read_markdown_at_commit(repo, parent, rel_path) if parent else None
                elif status == "D":
                    kind = EventKind.MEMORY_DELETED
                    parent = self._first_parent(repo, commit_sha)
                    before = self._read_markdown_at_commit(repo, parent, rel_path) if parent else None
                else:
                    continue

                events.append(
                    MemoryEvent(
                        event_id=f"{session_id}:{ordinal}",
                        kind=kind,
                        framework=self.framework,
                        agent_id=agent_id,
                        session_id=session_id,
                        timestamp=commit_time,
                        source="letta-git-import",
                        memory_id=memory_id,
                        before=before,
                        after=after,
                        metadata={"commit": commit_sha, "subject": subject, "path": rel_path, **shared_metadata},
                    )
                )

        events.append(
            MemoryEvent(
                event_id=f"{session_id}:end",
                kind=EventKind.SESSION_ENDED,
                framework=self.framework,
                agent_id=agent_id,
                session_id=session_id,
                timestamp=last_timestamp,
                source="letta-git-import",
                metadata={"memory_dir": str(repo), **shared_metadata},
            )
        )
        return events

    def _normalize(self, payload: dict[str, Any], line_number: int) -> MemoryEvent:
        kind_value = payload.get("kind") or payload.get("event_type")
        if kind_value not in LETTA_KIND_MAP:
            raise AdapterError(f"Unsupported Letta event kind on line {line_number}: {kind_value!r}")

        framework = payload.get("framework", self.framework)
        session_id = payload.get("session_id")
        agent_id = payload.get("agent_id")
        event_id = payload.get("event_id") or f"{session_id}:{line_number}"
        if not session_id or not agent_id:
            raise AdapterError(f"Missing session_id or agent_id on line {line_number}")

        return MemoryEvent(
            event_id=event_id,
            kind=LETTA_KIND_MAP[kind_value],
            framework=framework,
            agent_id=agent_id,
            session_id=session_id,
            timestamp=payload.get("timestamp", utc_now_iso()),
            source=payload.get("source", "letta-trace"),
            memory_id=payload.get("memory_id"),
            related_memory_ids=list(payload.get("related_memory_ids", [])),
            query=payload.get("query"),
            before=payload.get("before"),
            after=payload.get("after"),
            metadata=dict(payload.get("metadata", {})),
            latency_ms=payload.get("latency_ms"),
            tokens_loaded=payload.get("tokens_loaded"),
            score=payload.get("score"),
        )

    def _load_runtime_trace_for_capture(
        self,
        path: str | Path,
        capture: "LettaCapture",
        ended_at: str,
    ) -> list[MemoryEvent]:
        loaded = self.load_events(path)
        filtered: list[MemoryEvent] = []
        for ordinal, event in enumerate(loaded, start=1):
            if event.kind in {EventKind.SESSION_STARTED, EventKind.SESSION_ENDED}:
                continue
            if event.agent_id != capture.agent_id:
                continue
            if event.timestamp < capture.started_at or event.timestamp > ended_at:
                continue
            filtered.append(
                MemoryEvent(
                    event_id=f"{capture.capture_id}:runtime:{ordinal}",
                    kind=event.kind,
                    framework=event.framework,
                    agent_id=capture.agent_id,
                    session_id=capture.capture_id,
                    timestamp=event.timestamp,
                    source=event.source,
                    memory_id=event.memory_id,
                    related_memory_ids=list(event.related_memory_ids),
                    query=event.query,
                    before=event.before,
                    after=event.after,
                    metadata={
                        **event.metadata,
                        "capture_id": capture.capture_id,
                        "conversation_id": capture.conversation_id,
                        "capture_mode": "runtime-trace",
                    },
                    latency_ms=event.latency_ms,
                    tokens_loaded=event.tokens_loaded,
                    score=event.score,
                )
            )
        return filtered

    def _git_output(self, repo: Path, args: list[str]) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout

    def _first_parent(self, repo: Path, commit_sha: str) -> str | None:
        completed = subprocess.run(
            ["git", "-C", str(repo), "rev-list", "--parents", "-n", "1", commit_sha],
            check=True,
            capture_output=True,
            text=True,
        )
        parts = completed.stdout.strip().split()
        return parts[1] if len(parts) > 1 else None

    def _read_markdown_at_commit(self, repo: Path, commit_sha: str | None, rel_path: str) -> dict[str, Any] | None:
        if not commit_sha:
            return None
        completed = subprocess.run(
            ["git", "-C", str(repo), "show", f"{commit_sha}:{rel_path}"],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return None
        return self._parse_markdown_memory(completed.stdout)

    def _parse_markdown_memory(self, text: str) -> dict[str, Any]:
        frontmatter, content = self._split_frontmatter(text)
        return {
            "content": content.strip(),
            "attributes": {},
            "frontmatter": frontmatter,
        }

    def _split_frontmatter(self, text: str) -> tuple[dict[str, Any], str]:
        if not text.startswith("---\n"):
            return {}, text
        parts = text.split("\n---\n", 1)
        if len(parts) != 2:
            return {}, text
        raw_frontmatter = parts[0][4:]
        content = parts[1]
        attributes: dict[str, Any] = {}
        for line in raw_frontmatter.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            attributes[key.strip()] = value.strip()
        return attributes, content

    def _is_memory_markdown(self, rel_path: str) -> bool:
        path = Path(rel_path)
        if path.suffix.lower() != ".md":
            return False
        return not any(part.startswith(".") for part in path.parts)

    def _agent_id_from_memory_dir(self, repo: Path) -> str:
        parent = repo.parent
        if parent.name.startswith("agent-"):
            return parent.name
        return repo.name


@dataclass(slots=True)
class LettaLocalState:
    home: Path = Path.home()
    workspace_root: Path = Path.cwd()

    @property
    def root_dir(self) -> Path:
        return self.home / ".letta"

    @property
    def agents_dir(self) -> Path:
        return self.root_dir / "agents"

    @property
    def captures_dir(self) -> Path:
        return self.workspace_root / ".memfs_doctor" / "captures"

    @property
    def settings_path(self) -> Path:
        return self.root_dir / "settings.json"

    def get_last_session(self, agent_id: str) -> "LettaSessionContext":
        conversation_id = "unknown"
        if self.settings_path.exists():
            try:
                payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            last_session = payload.get("lastSession", {})
            if last_session.get("agentId") == agent_id:
                conversation_id = str(last_session.get("conversationId", "default"))
            else:
                sessions_by_server = payload.get("sessionsByServer", {})
                for server_payload in sessions_by_server.values():
                    if server_payload.get("agentId") == agent_id:
                        conversation_id = str(server_payload.get("conversationId", "default"))
                        break
        return LettaSessionContext(agent_id=agent_id, conversation_id=conversation_id)

    def save_capture(self, capture: "LettaCapture") -> None:
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        path = self.captures_dir / f"{capture.capture_id}.json"
        path.write_text(json.dumps(capture.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def load_capture(self, capture_id: str) -> "LettaCapture":
        path = self.captures_dir / f"{capture_id}.json"
        if not path.exists():
            raise AdapterError(f"Unknown Letta capture id: {capture_id}")
        return LettaCapture.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def delete_capture(self, capture_id: str) -> None:
        path = self.captures_dir / f"{capture_id}.json"
        if path.exists():
            path.unlink()

    def list_captures(self) -> list["LettaCapture"]:
        if not self.captures_dir.exists():
            return []
        captures: list[LettaCapture] = []
        for path in sorted(self.captures_dir.glob("*.json")):
            captures.append(LettaCapture.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return captures


@dataclass(slots=True)
class LettaAgent:
    agent_id: str
    memory_dir: Path


@dataclass(slots=True)
class LettaSessionContext:
    agent_id: str
    conversation_id: str


@dataclass(slots=True)
class LettaCapture:
    capture_id: str
    agent_id: str
    memory_dir: Path
    base_head: str
    started_at: str
    conversation_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "agent_id": self.agent_id,
            "memory_dir": str(self.memory_dir),
            "base_head": self.base_head,
            "started_at": self.started_at,
            "conversation_id": self.conversation_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LettaCapture":
        return cls(
            capture_id=payload["capture_id"],
            agent_id=payload["agent_id"],
            memory_dir=Path(payload["memory_dir"]),
            base_head=payload["base_head"],
            started_at=payload["started_at"],
            conversation_id=payload.get("conversation_id", "unknown"),
        )
