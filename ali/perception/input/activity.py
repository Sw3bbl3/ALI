"""Input activity perception module."""

from __future__ import annotations

import asyncio

from ali.core.event_bus import Event, EventBus


class InputActivityMonitor:
    """Tracks keyboard/mouse activity and emits input events.

    TODO: Hook into OS-level input events locally.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    async def run(self) -> None:
        """Perception loop placeholder."""
        while True:
            await asyncio.sleep(6)
            event = Event(
                event_type="input.activity",
                payload={"status": "placeholder"},
                source="perception.input",
            )
            await self._event_bus.publish(event)
