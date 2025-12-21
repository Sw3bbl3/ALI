"""Event bus for ALI modules.

The event bus provides a lightweight publish/subscribe mechanism so
perception, interpretation, reasoning, and action modules can communicate
without tight coupling.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List


@dataclass(frozen=True)
class Event:
    """A structured event emitted by ALI modules."""

    event_type: str
    payload: Dict[str, Any]
    source: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """Minimal async event bus for publish/subscribe.

    TODO: Add persistence, backpressure metrics, and replay support.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register an async handler for an event type."""
        async with self._lock:
            self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event to all matching subscribers."""
        async with self._lock:
            handlers = list(self._subscribers.get(event.event_type, []))
            handlers += self._subscribers.get("*", [])

        if not handlers:
            return

        await asyncio.gather(*(handler(event) for handler in handlers))
