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
    salience: float = 0.0


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
        if item.salience <= 0:
            item.salience = self._infer_salience(item.key, item.payload)
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

    def recall_salient(self, limit: int = 5) -> List[MemoryItem]:
        """Recall salient memories using a recency + salience score."""
        self._apply_decay()
        scored = sorted(
            self.short_term,
            key=self._salience_score,
            reverse=True,
        )
        return scored[:limit]

    def summarize(self) -> Dict[str, int]:
        """Summarize recent memory counts by key."""
        self._apply_decay()
        summary: Dict[str, int] = {}
        for item in self.short_term:
            summary[item.key] = summary.get(item.key, 0) + 1
        return summary

    def summarize_item(self, item: MemoryItem) -> str:
        """Create a concise, stable summary for a memory item."""
        payload = item.payload
        if item.key == "intent.updated":
            intent = payload.get("intent", "unknown")
            confidence = payload.get("confidence")
            if confidence is not None:
                return f"intent={intent} conf={float(confidence):.2f}"
            return f"intent={intent}"
        if item.key == "action.completed":
            action_type = payload.get("action_type", "unknown")
            return f"action.completed={action_type}"
        if item.key == "ali.response":
            response_type = payload.get("response_type", "unknown")
            title = payload.get("title")
            if title:
                return f"ali.response={response_type} ({title})"
            return f"ali.response={response_type}"
        if item.key == "action.requested":
            action_type = payload.get("action_type", "unknown")
            return f"action.requested={action_type}"
        if "transcript" in payload:
            snippet = str(payload.get("transcript", "")).strip()
            if snippet:
                return f"transcript={snippet[:40]}".rstrip()
        if "emotion" in payload:
            emotion = payload.get("emotion")
            if emotion:
                return f"emotion={emotion}"
        return item.key

    def _apply_decay(self) -> None:
        cutoff = time.time() - self.decay_seconds
        self.short_term = [item for item in self.short_term if item.timestamp >= cutoff]

    def _infer_salience(self, key: str, payload: Dict[str, Any]) -> float:
        if key == "action.completed":
            return 1.25
        if key == "ali.response":
            return 1.1
        if key == "action.requested":
            return 0.85
        if key == "intent.updated":
            confidence = float(payload.get("confidence", 0.0))
            return 0.35 + min(confidence, 1.0) * 0.6
        if key == "emotion.updated":
            return 0.5
        return 0.2

    def _salience_score(self, item: MemoryItem) -> float:
        age = time.time() - item.timestamp
        recency = max(0.0, 1.0 - (age / self.decay_seconds))
        return item.salience + (recency * 0.5)
