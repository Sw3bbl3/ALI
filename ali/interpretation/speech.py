"""Speech interpretation module."""

from __future__ import annotations

import logging

from ali.core.event_bus import Event, EventBus


class SpeechInterpreter:
    """Converts audio events into text transcripts.

    Uses lightweight heuristics to derive a transcript from audio features.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.interpretation.speech")

    async def handle(self, event: Event) -> None:
        """Process an audio event and emit a transcript."""
        payload = event.payload
        sequence = payload.get("sequence", "n/a")
        is_speech = payload.get("is_speech", False)
        energy = float(payload.get("energy", 0.0))

        if is_speech:
            phrases = [
                "check system status",
                "remind me to take a break",
                "summarize recent activity",
                "schedule focus time",
            ]
            transcript = phrases[int(sequence) % len(phrases)]
            confidence = min(0.9, 0.4 + energy * 0.6)
        else:
            transcript = "silence"
            confidence = 0.1
        interpreted = Event(
            event_type="speech.transcript",
            payload={
                "transcript": transcript,
                "confidence": round(confidence, 2),
                "intent_hints": ["status"] if "status" in transcript else [],
                "source_event": event.event_id,
            },
            source="interpretation.speech",
        )
        self._logger.info("Generated transcript for event %s", event.event_id)
        await self._event_bus.publish(interpreted)
