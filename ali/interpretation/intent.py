"""Intent interpretation module."""

from __future__ import annotations

import logging

from ali.core.event_bus import Event, EventBus


class IntentClassifier:
    """Infers user intent probability vectors.

    Combines signals from multiple modalities.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.interpretation.intent")
        self._context_tags: set[str] = set()
        self._last_emotion: str = "neutral"

    async def handle(self, event: Event) -> None:
        """Process an event and update intent state."""
        if event.event_type == "context.tagged":
            self._context_tags = set(event.payload.get("tags", []))
        if event.event_type == "emotion.detected":
            self._last_emotion = event.payload.get("emotion", "neutral")

        transcript = ""
        confidence = 0.3
        intent = "idle"

        if event.event_type == "speech.transcript":
            transcript = event.payload.get("transcript", "")
            confidence = float(event.payload.get("confidence", 0.3))
            intent = self._intent_from_transcript(transcript)
        elif event.event_type == "context.tagged":
            intent = self._intent_from_context()
            confidence = 0.55 if intent != "idle" else 0.3
        elif event.event_type == "emotion.detected":
            intent = self._intent_from_emotion()
            confidence = 0.5 if intent != "idle" else 0.3

        if "speech_detected" in self._context_tags and intent == "idle":
            intent = "assist"
            confidence = max(confidence, 0.6)

        interpreted = Event(
            event_type="intent.updated",
            payload={
                "intent": intent,
                "confidence": confidence,
                "context_tags": list(self._context_tags),
                "emotion": self._last_emotion,
                "transcript": transcript,
                "source_event": event.event_id,
            },
            source="interpretation.intent",
        )
        self._logger.info("Intent updated to '%s' (%.2f)", intent, confidence)
        await self._event_bus.publish(interpreted)

    def _intent_from_transcript(self, transcript: str) -> str:
        transcript = transcript.lower()
        if "status" in transcript:
            return "status_check"
        if "remind" in transcript or "break" in transcript:
            return "wellbeing"
        if "schedule" in transcript or "focus" in transcript:
            return "focus_planning"
        if "summarize" in transcript:
            return "summary"
        if transcript and transcript != "silence":
            return "assist"
        return "idle"

    def _intent_from_context(self) -> str:
        if "high_load" in self._context_tags:
            return "performance_check"
        if "active_input" in self._context_tags:
            return "do_not_disturb"
        return "idle"

    def _intent_from_emotion(self) -> str:
        if self._last_emotion in {"tired", "calm"}:
            return "wellbeing"
        if self._last_emotion in {"excited", "curious"}:
            return "assist"
        return "idle"
