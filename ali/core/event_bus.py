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
        handler_timeout: float = 2.0,
        worker_count: int = 4,
        queue_maxsize: int = 500,
    ) -> None:
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._lock = asyncio.Lock()
        self._history: Deque[Event] = deque(maxlen=max_history)
        self._in_flight = asyncio.Semaphore(max_in_flight)
        self._backpressure_timeout = backpressure_timeout
        self._handler_timeout = handler_timeout
        self._queue: asyncio.Queue[tuple[EventHandler, Event, float]] = asyncio.Queue(
            maxsize=queue_maxsize
        )
        self._worker_count = max(1, worker_count)
        self._worker_tasks: List[asyncio.Task[None]] = []
        self._published_count = 0
        self._dropped_count = 0
        self._error_count = 0
        self._timeout_count = 0
        self._handler_timeouts: Dict[str, int] = {}
        self._handler_errors: Dict[str, int] = {}
        self._handler_lag: Dict[str, float] = {}
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
        self._ensure_workers()
        await asyncio.gather(
            *(self._enqueue_handler(handler, event, start) for handler in handlers)
        )
        self._last_publish_latency = time.monotonic() - start
        self._last_publish_time = time.time()

    def _ensure_workers(self) -> None:
        if self._worker_tasks:
            return
        loop = asyncio.get_running_loop()
        self._worker_tasks = [
            loop.create_task(self._worker_loop(), name=f"event-bus-worker-{index}")
            for index in range(self._worker_count)
        ]

    async def _enqueue_handler(
        self, handler: EventHandler, event: Event, start_time: float
    ) -> None:
        try:
            await asyncio.wait_for(
                self._queue.put((handler, event, start_time)),
                timeout=self._backpressure_timeout,
            )
        except asyncio.TimeoutError:
            self._dropped_count += 1
            self._logger.warning("Dropped event %s due to backpressure", event.event_id)
            return

    async def _worker_loop(self) -> None:
        while True:
            handler, event, enqueued_at = await self._queue.get()
            handler_key = self._handler_key(handler)
            lag = time.monotonic() - enqueued_at
            self._handler_lag[handler_key] = lag
            try:
                await self._invoke_handler(handler, event, handler_key)
            finally:
                self._queue.task_done()

    async def _invoke_handler(
        self, handler: EventHandler, event: Event, handler_key: str
    ) -> None:
        try:
            await asyncio.wait_for(
                self._in_flight.acquire(), timeout=self._backpressure_timeout
            )
        except asyncio.TimeoutError:
            self._dropped_count += 1
            self._logger.warning("Dropped event %s due to backpressure", event.event_id)
            return
        try:
            await asyncio.wait_for(handler(event), timeout=self._handler_timeout)
        except asyncio.TimeoutError:
            self._timeout_count += 1
            self._handler_timeouts[handler_key] = (
                self._handler_timeouts.get(handler_key, 0) + 1
            )
            self._logger.warning(
                "Handler timeout for event %s after %.2fs",
                event.event_id,
                self._handler_timeout,
            )
        except Exception:  # pragma: no cover - defensive logging
            self._error_count += 1
            self._handler_errors[handler_key] = self._handler_errors.get(handler_key, 0) + 1
            self._logger.exception("Handler error for event %s", event.event_id)
        finally:
            self._in_flight.release()

    @staticmethod
    def _handler_key(handler: EventHandler) -> str:
        return f"{handler.__module__}.{handler.__qualname__}"

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
            "timeouts": self._timeout_count,
            "last_publish_latency": round(self._last_publish_latency, 4),
            "last_publish_time": self._last_publish_time,
            "history_size": len(self._history),
            "queue_depth": self._queue.qsize(),
            "handler_lag": {key: round(value, 4) for key, value in self._handler_lag.items()},
            "handler_timeouts": dict(self._handler_timeouts),
            "handler_errors": dict(self._handler_errors),
        }

    def recent_events(self, limit: int = 5) -> List[Event]:
        """Return the most recent events for context."""
        if limit <= 0:
            return []
        return list(self._history)[-limit:]
