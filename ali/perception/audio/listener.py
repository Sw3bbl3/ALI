"""Audio perception module."""

from __future__ import annotations

import asyncio
import logging
import math
import time

from ali.core.event_bus import Event, EventBus


class AudioListener:
    """Listens to microphone input and emits audio events.

    Emits synthetic audio features to simulate local capture and buffering.
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
            energy = abs(math.sin(self._counter / 2.5))
            is_speech = energy > 0.6
            spectral_flatness = round(0.2 + (1 - energy) * 0.6, 3)
            event = Event(
                event_type="audio.sampled",
                payload={
                    "sequence": self._counter,
                    "status": "captured",
                    "sample_rate_hz": 16_000,
                    "duration_ms": 1200,
                    "energy": round(energy, 3),
                    "spectral_flatness": spectral_flatness,
                    "is_speech": is_speech,
                    "timestamp": time.time(),
                },
                source="perception.audio",
            )
            self._logger.info("Captured audio sample %s", self._counter)
            await self._event_bus.publish(event)
