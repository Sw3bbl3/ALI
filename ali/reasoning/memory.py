"""Memory subsystem for ALI."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryItem:
    """Represents a memory entry."""

    key: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class MemoryStore:
    """Stores short-term and long-term memories.

    Supports decay, retrieval, and simple promotion to long-term storage.
    """

    short_term: List[MemoryItem] = field(default_factory=list)
    long_term: List[MemoryItem] = field(default_factory=list)
    max_short_term: int = 50
    decay_seconds: float = 120.0

    def add_short_term(self, item: MemoryItem) -> None:
        """Add a memory item to short-term storage."""
        self.short_term.append(item)
        self._apply_decay()
        if len(self.short_term) > self.max_short_term:
            overflow = self.short_term[:-self.max_short_term]
            self.short_term = self.short_term[-self.max_short_term :]
            self.long_term.extend(overflow)

    def add_long_term(self, item: MemoryItem) -> None:
        """Add a memory item to long-term storage."""
        self.long_term.append(item)

    def recall(self, key: Optional[str] = None, limit: int = 5) -> List[MemoryItem]:
        """Recall recent memories matching a key."""
        self._apply_decay()
        candidates = self.short_term
        if key:
            candidates = [item for item in candidates if item.key == key]
        return candidates[-limit:]

    def summarize(self) -> Dict[str, int]:
        """Summarize recent memory counts by key."""
        self._apply_decay()
        summary: Dict[str, int] = {}
        for item in self.short_term:
            summary[item.key] = summary.get(item.key, 0) + 1
        return summary

    def _apply_decay(self) -> None:
        cutoff = time.time() - self.decay_seconds
        self.short_term = [item for item in self.short_term if item.timestamp >= cutoff]
