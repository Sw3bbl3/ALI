"""Input activity perception module."""

from __future__ import annotations

import asyncio
import logging
import time

from ali.core.event_bus import Event, EventBus


class InputActivityMonitor:
    """Tracks keyboard/mouse activity and emits input events.

    Emits synthetic activity states that mimic local input activity.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._counter = 0
        self._logger = logging.getLogger("ali.perception.input")

    async def run(self) -> None:
        """Perception loop placeholder."""
        while True:
            await asyncio.sleep(5)
            self._counter += 1
            activity = "typing" if self._counter % 3 == 0 else "idle"
            activity_score = 0.8 if activity == "typing" else 0.2
            event = Event(
                event_type="input.activity",
                payload={
                    "sequence": self._counter,
                    "status": "detected",
                    "activity": activity,
                    "activity_score": activity_score,
                    "timestamp": time.time(),
                },
                source="perception.input",
            )
            self._logger.info("Observed input activity %s", self._counter)
            await self._event_bus.publish(event)
