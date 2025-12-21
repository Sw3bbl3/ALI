"""Orchestrator to manage ALI module lifecycle."""

from __future__ import annotations

import asyncio
from typing import List

from ali.core.event_bus import EventBus
from ali.core.permissions import PermissionGate
from ali.core.scheduler import Scheduler
from ali.perception.audio.listener import AudioListener
from ali.perception.vision.camera import CameraSensor
from ali.perception.input.activity import InputActivityMonitor
from ali.perception.system.metrics import SystemMetricsCollector


class Orchestrator:
    """Bootstraps and supervises ALI modules.

    TODO: Add dynamic module loading, health checks, and fault recovery.
    """

    def __init__(self) -> None:
        self.event_bus = EventBus()
        self.scheduler = Scheduler()
        self.permissions = PermissionGate()
        self._modules: List[object] = []

    def _init_modules(self) -> None:
        """Initialize core perception modules."""
        self._modules = [
            AudioListener(self.event_bus),
            CameraSensor(self.event_bus),
            InputActivityMonitor(self.event_bus),
            SystemMetricsCollector(self.event_bus),
        ]

    async def start(self) -> None:
        """Start the orchestrator and module loops."""
        self._init_modules()
        for module in self._modules:
            self.scheduler.schedule(module.run)

        await self._run_forever()

    async def _run_forever(self) -> None:
        """Keep the orchestrator alive until interrupted."""
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Stop all modules and clean up."""
        await self.scheduler.shutdown()
