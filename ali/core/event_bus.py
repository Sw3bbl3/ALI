"""Event bus for ALI modules.

The event bus provides a lightweight publish/subscribe mechanism so
perception, interpretation, reasoning, and action modules can communicate
without tight coupling.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Deque, Dict, List, Optional
from uuid import uuid4


@dataclass(frozen=True)
class Event:
    """A structured event emitted by ALI modules."""

    event_type: str
    payload: Dict[str, Any]
    source: str
    event_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """Minimal async event bus for publish/subscribe.

    Provides in-memory persistence, backpressure metrics, and replay support.
    """

    def __init__(
        self,
        max_history: int = 500,
        max_in_flight: int = 50,
        backpressure_timeout: float = 0.25,
    ) -> None:
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._lock = asyncio.Lock()
        self._history: Deque[Event] = deque(maxlen=max_history)
        self._in_flight = asyncio.Semaphore(max_in_flight)
        self._backpressure_timeout = backpressure_timeout
        self._published_count = 0
        self._dropped_count = 0
        self._error_count = 0
        self._last_publish_latency = 0.0
        self._last_publish_time = 0.0
        self._logger = logging.getLogger("ali.event_bus")

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register an async handler for an event type."""
        async with self._lock:
            self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event to all matching subscribers."""
        async with self._lock:
            handlers = list(self._subscribers.get(event.event_type, []))
            handlers += self._subscribers.get("*", [])

        self._history.append(event)
        self._published_count += 1
        if not handlers:
            return

        start = time.monotonic()
        await asyncio.gather(*(self._invoke_handler(handler, event) for handler in handlers))
        self._last_publish_latency = time.monotonic() - start
        self._last_publish_time = time.time()

    async def _invoke_handler(self, handler: EventHandler, event: Event) -> None:
        try:
            await asyncio.wait_for(self._in_flight.acquire(), timeout=self._backpressure_timeout)
        except asyncio.TimeoutError:
            self._dropped_count += 1
            self._logger.warning("Dropped event %s due to backpressure", event.event_id)
            return
        try:
            await handler(event)
        except Exception:  # pragma: no cover - defensive logging
            self._error_count += 1
            self._logger.exception("Handler error for event %s", event.event_id)
        finally:
            self._in_flight.release()

    async def replay(
        self,
        event_type: str,
        handler: EventHandler,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> None:
        """Replay stored events matching the type to a handler."""
        replayed = 0
        for event in list(self._history):
            if event_type != "*" and event.event_type != event_type:
                continue
            if since and event.created_at < since:
                continue
            await handler(event)
            replayed += 1
            if limit and replayed >= limit:
                break

    def metrics(self) -> Dict[str, Any]:
        """Return a snapshot of event bus metrics."""
        return {
            "published": self._published_count,
            "dropped": self._dropped_count,
            "errors": self._error_count,
            "last_publish_latency": round(self._last_publish_latency, 4),
            "last_publish_time": self._last_publish_time,
            "history_size": len(self._history),
        }
