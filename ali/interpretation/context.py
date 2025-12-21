"""Context tagging module."""

from __future__ import annotations

import logging

from ali.core.event_bus import Event, EventBus


class ContextTagger:
    """Adds semantic context tags to events.

    TODO: Integrate context graph and user habit signals.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.interpretation.context")

    async def handle(self, event: Event) -> None:
        """Process an event and enrich with tags."""
        tags = [event.event_type.split(".")[0], "local", "telemetry"]
        interpreted = Event(
            event_type="context.tagged",
            payload={
                "tags": tags,
                "source_event": event.event_id,
            },
            source="interpretation.context",
        )
        self._logger.info("Tagged event %s with %s", event.event_id, tags)
        await self._event_bus.publish(interpreted)
