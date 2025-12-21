"""Memory subsystem for ALI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MemoryItem:
    """Represents a memory entry."""

    key: str
    payload: Dict[str, Any]


@dataclass
class MemoryStore:
    """Stores short-term and long-term memories.

    TODO: Add persistence, decay, and retrieval strategies.
    """

    short_term: List[MemoryItem] = field(default_factory=list)
    long_term: List[MemoryItem] = field(default_factory=list)

    def add_short_term(self, item: MemoryItem) -> None:
        """Add a memory item to short-term storage."""
        self.short_term.append(item)

    def add_long_term(self, item: MemoryItem) -> None:
        """Add a memory item to long-term storage."""
        self.long_term.append(item)
