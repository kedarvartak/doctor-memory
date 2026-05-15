from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from memfs_doctor.core.events import MemoryEvent


class AdapterError(RuntimeError):
    """Raised when an adapter cannot normalize a framework trace."""


class BaseAdapter(ABC):
    framework: str

    @abstractmethod
    def load_events(self, path: str | Path) -> list[MemoryEvent]:
        """Load framework-specific trace data into normalized events."""

