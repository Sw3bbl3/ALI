"""Scheduling utilities for ALI modules."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional


@dataclass
class TaskSpec:
    """Defines a scheduled coroutine factory."""

    name: str
    coro_factory: Callable[[], Awaitable[None]]
    priority: int = 100
    power_cost: float = 1.0
    restart: bool = True
    max_restarts: int = 3


@dataclass
class TaskState:
    """Tracks runtime task state."""

    status: str = "pending"
    last_error: Optional[str] = None
    restarts: int = 0
    last_heartbeat: float = field(default_factory=time.monotonic)


class Scheduler:
    """Simple task scheduler for module loops.

    Includes priority ordering, light throttling, and power budgeting.
    """

    def __init__(
        self,
        power_budget: float = 10.0,
        load_threshold: float = 4.0,
        throttle_seconds: float = 0.5,
        heartbeat_interval: float = 2.0,
    ) -> None:
        self._tasks: List[asyncio.Task] = []
        self._task_specs: List[TaskSpec] = []
        self._task_state: Dict[str, TaskState] = {}
        self._power_budget = power_budget
        self._power_used = 0.0
        self._load_threshold = load_threshold
        self._throttle_seconds = throttle_seconds
        self._heartbeat_interval = heartbeat_interval
        self._logger = logging.getLogger("ali.scheduler")

    def schedule(
        self,
        coro_factory: Callable[[], Awaitable[None]],
        name: Optional[str] = None,
        priority: int = 100,
        power_cost: float = 1.0,
        restart: bool = True,
        max_restarts: int = 3,
    ) -> None:
        """Schedule a coroutine factory on the event loop."""
        task_name = name or getattr(coro_factory, "__name__", "module")
        spec = TaskSpec(
            name=task_name,
            coro_factory=coro_factory,
            priority=priority,
            power_cost=power_cost,
            restart=restart,
            max_restarts=max_restarts,
        )
        self._task_specs.append(spec)
        self._task_specs.sort(key=lambda item: item.priority)
        self._ensure_task(spec)

    async def shutdown(self) -> None:
        """Cancel all scheduled tasks and wait for cleanup."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._task_state.clear()
        self._power_used = 0.0

    def health_snapshot(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Return task state and last error details."""
        return {
            name: {
                "status": state.status,
                "last_error": state.last_error,
                "restarts": str(state.restarts),
                "last_heartbeat": str(state.last_heartbeat),
            }
            for name, state in self._task_state.items()
        }

    def _ensure_task(self, spec: TaskSpec) -> None:
        state = self._task_state.setdefault(spec.name, TaskState())
        if state.status == "running":
            return
        if self._power_used + spec.power_cost > self._power_budget:
            state.status = "pending"
            self._logger.warning("Power budget exceeded; delaying %s", spec.name)
            return
        state.status = "running"
        self._power_used += spec.power_cost
        task = asyncio.create_task(self._run_task(spec))
        task.add_done_callback(lambda done: self._on_task_done(spec, done))
        self._tasks.append(task)

    async def _run_task(self, spec: TaskSpec) -> None:
        state = self._task_state[spec.name]
        while True:
            if self._should_throttle():
                await asyncio.sleep(self._throttle_seconds)
            state.last_heartbeat = time.monotonic()
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(state))
            try:
                await spec.coro_factory()
            finally:
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task
            break

    def _on_task_done(self, spec: TaskSpec, done: asyncio.Task) -> None:
        state = self._task_state[spec.name]
        self._power_used = max(self._power_used - spec.power_cost, 0.0)

        if done.cancelled():
            state.status = "cancelled"
            return

        exc = done.exception()
        if exc:
            state.last_error = str(exc)
            state.status = "failed"
            self._logger.error("Task %s failed: %s", spec.name, exc)
        if exc and spec.restart and state.restarts < spec.max_restarts:
            state.restarts += 1
            self._logger.info("Restarting %s (%s/%s)", spec.name, state.restarts, spec.max_restarts)
            self._ensure_task(spec)

    def _should_throttle(self) -> bool:
        if not hasattr(os, "getloadavg"):
            return False
        try:
            load = os.getloadavg()[0]
        except OSError:
            return False
        return load >= self._load_threshold

    async def _heartbeat_loop(self, state: TaskState) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            state.last_heartbeat = time.monotonic()
