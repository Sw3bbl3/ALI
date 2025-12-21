"""Speech interpretation module."""

from __future__ import annotations

import logging

from ali.core.event_bus import Event, EventBus


class SpeechInterpreter:
    """Converts audio events into text transcripts.

    TODO: Integrate local speech-to-text model.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.interpretation.speech")

    async def handle(self, event: Event) -> None:
        """Process an audio event and emit a transcript."""
        transcript = f"placeholder transcript for sample {event.payload.get('sequence', 'n/a')}"
        interpreted = Event(
            event_type="speech.transcript",
            payload={
                "transcript": transcript,
                "confidence": 0.42,
                "source_event": event.event_id,
            },
            source="interpretation.speech",
        )
        self._logger.info("Generated transcript for event %s", event.event_id)
        await self._event_bus.publish(interpreted)
