"""Intent interpretation module."""

from __future__ import annotations

import logging

from ali.core.event_bus import Event, EventBus


class IntentClassifier:
    """Infers user intent probability vectors.

    TODO: Combine signals from multiple modalities.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.interpretation.intent")

    async def handle(self, event: Event) -> None:
        """Process an event and update intent state."""
        intent = "assist" if event.event_type in {"speech.transcript", "context.tagged"} else "idle"
        confidence = 0.65 if intent == "assist" else 0.3
        interpreted = Event(
            event_type="intent.updated",
            payload={
                "intent": intent,
                "confidence": confidence,
                "source_event": event.event_id,
            },
            source="interpretation.intent",
        )
        self._logger.info("Intent updated to '%s' (%.2f)", intent, confidence)
        await self._event_bus.publish(interpreted)
