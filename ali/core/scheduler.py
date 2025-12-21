"""Scheduling utilities for ALI modules."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, List


class Scheduler:
    """Simple task scheduler for module loops.

    TODO: Add priority queues, throttling, and power budgeting.
    """

    def __init__(self) -> None:
        self._tasks: List[asyncio.Task] = []

    def schedule(self, coro_factory: Callable[[], Awaitable[None]]) -> None:
        """Schedule a coroutine factory on the event loop."""
        task = asyncio.create_task(coro_factory())
        self._tasks.append(task)

    async def shutdown(self) -> None:
        """Cancel all scheduled tasks and wait for cleanup."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
