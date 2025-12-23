"""Async input queue with backpressure handling."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass
class InputQueueMetrics:
    """Metrics for queued input processing."""

    enqueued: int
    dropped: int
    processed: int
    last_latency: float
    last_processed_time: float
    max_depth: int


class InputQueue(Generic[T]):
    """Queue inputs for serial or batched processing."""

    def __init__(
        self,
        handler: Callable[[T], Awaitable[None]],
        *,
        maxsize: int = 100,
        max_batch: int = 4,
        name: str = "input.queue",
    ) -> None:
        self._handler = handler
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)
        self._max_batch = max(1, max_batch)
        self._logger = logging.getLogger(name)
        self._task: asyncio.Task | None = None
        self._enqueued = 0
        self._dropped = 0
        self._processed = 0
        self._last_latency = 0.0
        self._last_processed_time = 0.0
        self._max_depth = 0

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def enqueue(self, item: T) -> bool:
        if self._queue.full():
            try:
                _ = self._queue.get_nowait()
                self._dropped += 1
                self._logger.warning("Dropped oldest input due to backpressure")
            except asyncio.QueueEmpty:
                pass
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            self._dropped += 1
            self._logger.warning("Dropped input because queue is full")
            return False
        self._enqueued += 1
        self._max_depth = max(self._max_depth, self._queue.qsize())
        return True

    def metrics(self) -> InputQueueMetrics:
        return InputQueueMetrics(
            enqueued=self._enqueued,
            dropped=self._dropped,
            processed=self._processed,
            last_latency=round(self._last_latency, 4),
            last_processed_time=self._last_processed_time,
            max_depth=self._max_depth,
        )

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()
            batch = [item]
            while len(batch) < self._max_batch:
                try:
                    batch.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            for entry in batch:
                start = time.monotonic()
                try:
                    await self._handler(entry)
                finally:
                    self._queue.task_done()
                    self._processed += 1
                    self._last_latency = time.monotonic() - start
                    self._last_processed_time = time.time()
