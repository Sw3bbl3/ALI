"""Orchestrator to manage ALI module lifecycle."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

from ali.core.event_bus import EventBus
from ali.core.event_logger import EventLogger
from ali.core.logging_setup import configure_logging
from ali.core.permissions import PermissionGate
from ali.core.scheduler import Scheduler
from ali.core.status import StatusReporter
from ali.action.coordinator import ActionCoordinator
from ali.interpretation.context import ContextTagger
from ali.interpretation.emotion import EmotionDetector
from ali.interpretation.intent import IntentClassifier
from ali.interpretation.speech import SpeechInterpreter
from ali.perception.audio.listener import AudioListener
from ali.perception.vision.camera import CameraSensor
from ali.perception.input.activity import InputActivityMonitor
from ali.perception.system.metrics import SystemMetricsCollector
from ali.reasoning.engine import ReasoningEngine


class Orchestrator:
    """Bootstraps and supervises ALI modules.

    TODO: Add dynamic module loading, health checks, and fault recovery.
    """

    def __init__(self) -> None:
        configure_logging(Path("ali/logs"))
        self.event_bus = EventBus()
        self.scheduler = Scheduler()
        self.permissions = PermissionGate()
        self._modules: List[object] = []
        self._event_logger = EventLogger()
        self._status_reporter = StatusReporter()
        self._action_coordinator = ActionCoordinator(self.event_bus)
        self._reasoning_engine = ReasoningEngine(self.event_bus, self.permissions)

    def _init_modules(self) -> None:
        """Initialize core perception modules."""
        self._modules = [
            AudioListener(self.event_bus),
            CameraSensor(self.event_bus),
            InputActivityMonitor(self.event_bus),
            SystemMetricsCollector(self.event_bus),
        ]

    async def _register_handlers(self) -> None:
        """Register interpretation and reasoning handlers on the event bus."""
        speech = SpeechInterpreter(self.event_bus)
        emotion = EmotionDetector(self.event_bus)
        context = ContextTagger(self.event_bus)
        intent = IntentClassifier(self.event_bus)

        await self.event_bus.subscribe("*", self._event_logger.handle)
        await self.event_bus.subscribe("*", self._status_reporter.handle_event)

        await self.event_bus.subscribe("audio.sampled", speech.handle)
        await self.event_bus.subscribe("audio.sampled", emotion.handle)
        await self.event_bus.subscribe("vision.frame", emotion.handle)
        await self.event_bus.subscribe("audio.sampled", context.handle)
        await self.event_bus.subscribe("vision.frame", context.handle)
        await self.event_bus.subscribe("input.activity", context.handle)
        await self.event_bus.subscribe("system.metrics", context.handle)
        await self.event_bus.subscribe("speech.transcript", intent.handle)
        await self.event_bus.subscribe("context.tagged", intent.handle)
        await self.event_bus.subscribe("intent.updated", self._reasoning_engine.handle)
        await self.event_bus.subscribe("action.requested", self._action_coordinator.handle)

    async def start(self) -> None:
        """Start the orchestrator and module loops."""
        self._init_modules()
        await self._register_handlers()
        for module in self._modules:
            self.scheduler.schedule(module.run)
        self.scheduler.schedule(self._status_reporter.run)

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
