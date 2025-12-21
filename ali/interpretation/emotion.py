"""Emotion interpretation module."""

from __future__ import annotations

import logging

from ali.core.event_bus import Event, EventBus


class EmotionDetector:
    """Detects emotion from audio or vision signals.

    Uses lightweight heuristics to infer emotion cues.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.interpretation.emotion")

    async def handle(self, event: Event) -> None:
        """Process an event and infer emotional cues."""
        emotion, confidence = self._infer_emotion(event)
        interpreted = Event(
            event_type="emotion.detected",
            payload={
                "emotion": emotion,
                "confidence": confidence,
                "source_event": event.event_id,
            },
            source="interpretation.emotion",
        )
        self._logger.info("Detected emotion '%s' from %s", emotion, event.event_type)
        await self._event_bus.publish(interpreted)

    def _infer_emotion(self, event: Event) -> tuple[str, float]:
        payload = event.payload
        if event.event_type == "audio.sampled":
            energy = float(payload.get("energy", 0.0))
            if energy > 0.75:
                return "excited", 0.7
            if energy > 0.5:
                return "focused", 0.6
            return "calm", 0.55
        if event.event_type == "vision.frame":
            motion = float(payload.get("motion_score", 0.0))
            brightness = float(payload.get("brightness", 0.0))
            if motion > 0.6:
                return "curious", 0.6
            if brightness < 0.3:
                return "tired", 0.5
            return "neutral", 0.5
        return "neutral", 0.4
