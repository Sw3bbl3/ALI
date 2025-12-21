"""System metrics perception module."""

from __future__ import annotations

import asyncio

from ali.core.event_bus import Event, EventBus


class SystemMetricsCollector:
    """Collects system metrics and emits telemetry events.

    TODO: Integrate CPU, memory, battery, and network readings.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    async def run(self) -> None:
        """Perception loop placeholder."""
        while True:
            await asyncio.sleep(10)
            event = Event(
                event_type="system.metrics",
                payload={"status": "placeholder"},
                source="perception.system",
            )
            await self._event_bus.publish(event)
