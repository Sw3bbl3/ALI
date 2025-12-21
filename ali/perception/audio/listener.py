"""Audio perception module."""

from __future__ import annotations

import asyncio
import logging
import time

from ali.core.event_bus import Event, EventBus


class AudioListener:
    """Listens to microphone input and emits audio events.

    TODO: Integrate local audio capture and buffering.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._counter = 0
        self._logger = logging.getLogger("ali.perception.audio")

    async def run(self) -> None:
        """Perception loop placeholder."""
        while True:
            await asyncio.sleep(3)
            self._counter += 1
            event = Event(
                event_type="audio.sampled",
                payload={
                    "sequence": self._counter,
                    "status": "captured",
                    "sample_rate_hz": 16_000,
                    "timestamp": time.time(),
                },
                source="perception.audio",
            )
            self._logger.info("Captured audio sample %s", self._counter)
            await self._event_bus.publish(event)
