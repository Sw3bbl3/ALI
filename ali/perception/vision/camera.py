"""Vision perception module."""

from __future__ import annotations

import asyncio

from ali.core.event_bus import Event, EventBus


class CameraSensor:
    """Captures camera frames and emits vision events.

    TODO: Integrate camera capture and frame pre-processing.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    async def run(self) -> None:
        """Perception loop placeholder."""
        while True:
            await asyncio.sleep(7)
            event = Event(
                event_type="vision.frame",
                payload={"status": "placeholder"},
                source="perception.vision",
            )
            await self._event_bus.publish(event)
