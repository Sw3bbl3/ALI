"""Vision perception module."""

from __future__ import annotations

import asyncio
import logging
import math
import time

from ali.core.event_bus import Event, EventBus


class CameraSensor:
    """Captures camera frames and emits vision events.

    Emits lightweight frame metadata to simulate local capture.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._counter = 0
        self._logger = logging.getLogger("ali.perception.vision")

    async def run(self) -> None:
        """Perception loop placeholder."""
        while True:
            await asyncio.sleep(4)
            self._counter += 1
            brightness = abs(math.cos(self._counter / 3.0))
            motion_score = abs(math.sin(self._counter / 4.0))
            event = Event(
                event_type="vision.frame",
                payload={
                    "sequence": self._counter,
                    "status": "captured",
                    "resolution": "640x480",
                    "brightness": round(brightness, 3),
                    "motion_score": round(motion_score, 3),
                    "timestamp": time.time(),
                },
                source="perception.vision",
            )
            self._logger.info("Captured frame %s", self._counter)
            await self._event_bus.publish(event)
