"""Priority-aware queue for latency-sensitive event processing."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Deque, Generic, TypeVar


T = TypeVar("T")


@dataclass
class PriorityQueueMetrics:
    """Metrics for prioritized queue processing."""

    enqueued: int
    dropped: int
    processed: int
    processed_high: int
    processed_normal: int
    last_latency: float
    last_processed_time: float
    max_depth: int
    high_depth: int
    normal_depth: int


class PrioritizedQueue(Generic[T]):
    """Process higher-priority items ahead of normal items on a tight tick."""

    def __init__(
        self,
        handler: Callable[[T], Awaitable[None]],
        priority_fn: Callable[[T], bool],
        *,
        maxsize: int = 200,
        max_batch: int = 8,
        tick_seconds: float = 0.001,
        name: str = "ali.priority.queue",
    ) -> None:
        self._handler = handler
        self._priority_fn = priority_fn
        self._maxsize = max(1, maxsize)
        self._max_batch = max(1, max_batch)
        self._tick_seconds = max(0.0, tick_seconds)
        self._high: Deque[T] = deque()
        self._normal: Deque[T] = deque()
        self._logger = logging.getLogger(name)
        self._enqueued = 0
        self._dropped = 0
        self._processed = 0
        self._processed_high = 0
        self._processed_normal = 0
        self._last_latency = 0.0
        self._last_processed_time = 0.0
        self._max_depth = 0

    def enqueue(self, item: T) -> bool:
        """Insert an item, evicting lower-priority work if needed."""
        is_high = self._priority_fn(item)
        if self._size() >= self._maxsize:
            if self._normal:
                self._normal.popleft()
            elif self._high:
                self._high.popleft()
            self._dropped += 1
            self._logger.warning("Dropped queued item due to backpressure")
        target = self._high if is_high else self._normal
        target.append(item)
        self._enqueued += 1
        self._max_depth = max(self._max_depth, self._size())
        return True

    async def run(self) -> None:
        """Continuously process queued items with millisecond-level ticks."""
        while True:
            batch = self._dequeue_batch()
            if not batch:
                await asyncio.sleep(self._tick_seconds)
                continue
            for item, is_high in batch:
                start = time.monotonic()
                await self._handler(item)
                self._processed += 1
                if is_high:
                    self._processed_high += 1
                else:
                    self._processed_normal += 1
                self._last_latency = time.monotonic() - start
                self._last_processed_time = time.time()
            await asyncio.sleep(self._tick_seconds)

    def metrics(self) -> PriorityQueueMetrics:
        """Return processing and backpressure metrics."""
        return PriorityQueueMetrics(
            enqueued=self._enqueued,
            dropped=self._dropped,
            processed=self._processed,
            processed_high=self._processed_high,
            processed_normal=self._processed_normal,
            last_latency=round(self._last_latency, 4),
            last_processed_time=self._last_processed_time,
            max_depth=self._max_depth,
            high_depth=len(self._high),
            normal_depth=len(self._normal),
        )

    def _dequeue_batch(self) -> list[tuple[T, bool]]:
        batch: list[tuple[T, bool]] = []
        while len(batch) < self._max_batch and self._high:
            batch.append((self._high.popleft(), True))
        while len(batch) < self._max_batch and self._normal:
            batch.append((self._normal.popleft(), False))
        return batch

    def _size(self) -> int:
        return len(self._high) + len(self._normal)
