"""Audio perception module."""

from __future__ import annotations

import asyncio

from ali.core.event_bus import Event, EventBus


class AudioListener:
    """Listens to microphone input and emits audio events.

    TODO: Integrate local audio capture and buffering.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    async def run(self) -> None:
        """Perception loop placeholder."""
        while True:
            await asyncio.sleep(5)
            event = Event(
                event_type="audio.sampled",
                payload={"status": "placeholder"},
                source="perception.audio",
            )
            await self._event_bus.publish(event)
