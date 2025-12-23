"""Intent interpretation module."""

from __future__ import annotations

import logging
import os
import re
import time

from ali.core.event_bus import Event, EventBus
from ali.core.priority_queue import PrioritizedQueue


class IntentClassifier:
    """Infers user intent probability vectors.

    Combines signals from multiple modalities.
    """

    _TOKEN_PATTERN = re.compile(r"[a-z']+")
    _INTENT_KEYWORDS: dict[str, dict[str, float]] = {
        "status_check": {
            "status": 1.2,
            "health": 1.0,
            "metrics": 0.9,
            "cpu": 0.7,
            "memory": 0.7,
            "system": 0.6,
            "performance": 0.6,
        },
        "focus_planning": {
            "focus": 1.1,
            "schedule": 1.0,
            "plan": 0.8,
            "agenda": 0.8,
            "deadline": 0.7,
            "block": 0.6,
            "quiet": 0.5,
        },
        "wellbeing": {
            "break": 1.1,
            "rest": 1.0,
            "stretch": 0.9,
            "hydrate": 0.8,
            "tired": 0.8,
            "remind": 0.7,
        },
        "summary": {
            "summary": 1.2,
            "summarize": 1.1,
            "recap": 1.0,
            "digest": 0.9,
            "brief": 0.8,
        },
        "assist": {
            "help": 0.7,
            "assist": 0.7,
            "question": 0.6,
            "can": 0.4,
        },
    }

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.interpretation.intent")
        self._context_tags: set[str] = set()
        self._last_emotion: str = "neutral"
        self._last_transcript: str = ""
        self._last_transcript_time: float = 0.0
        self._recent_transcript_window = 60.0
        self._sticky_intent: str | None = None
        self._silence_timeout_seconds = float(os.getenv("ALI_ASSIST_SILENCE_TIMEOUT", "20"))
        tick_ms = float(os.getenv("ALI_INTENT_TICK_MS", "1"))
        self._queue = PrioritizedQueue(
            self._process_event,
            self._is_user_input,
            maxsize=250,
            max_batch=6,
            tick_seconds=max(tick_ms / 1000.0, 0.0005),
            name="ali.interpretation.intent.queue",
        )

    async def handle(self, event: Event) -> None:
        """Queue events for millisecond-priority intent processing."""
        if not self._queue.enqueue(event):
            self._logger.warning("Intent event dropped due to queue backpressure")

    async def run(self) -> None:
        """Run the intent processing loop on a tight tick."""
        await self._queue.run()

    async def _process_event(self, event: Event) -> None:
        """Process an event and update intent state."""
        if event.event_type == "context.tagged":
            self._context_tags = set(event.payload.get("tags", []))
        if event.event_type == "emotion.detected":
            self._last_emotion = event.payload.get("emotion", "neutral")
        if event.event_type == "action.completed":
            self._sticky_intent = None

        transcript = ""
        intent = "idle"
        confidence = 0.3
        clear_sticky = False

        if event.event_type == "speech.transcript":
            transcript = event.payload.get("transcript", "")
            raw_confidence = float(event.payload.get("confidence", 0.3))
            intent, confidence = self._intent_from_transcript(transcript, raw_confidence)
            if transcript:
                self._last_transcript = transcript
                self._last_transcript_time = time.monotonic()
            if transcript.strip().lower() == "silence":
                clear_sticky = True
        elif event.event_type == "context.tagged":
            intent, confidence = self._intent_from_context()
            if "idle_input" in self._context_tags and self._silence_timeout_elapsed():
                clear_sticky = True
        elif event.event_type == "emotion.detected":
            intent, confidence = self._intent_from_emotion()

        if "speech_detected" in self._context_tags and intent == "idle":
            intent = "assist"
            confidence = max(confidence, 0.6)

        if clear_sticky:
            self._sticky_intent = None

        if intent == "assist":
            self._sticky_intent = "assist"

        if intent == "idle" and self._sticky_intent == "assist":
            intent = "assist"
            confidence = max(confidence, 0.55)

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

    @staticmethod
    def _is_user_input(event: Event) -> bool:
        if event.event_type == "speech.transcript":
            return True
        return event.source in {"cli.input", "web_ui.input"}

    def _intent_from_transcript(self, transcript: str, raw_confidence: float) -> tuple[str, float]:
        transcript = transcript.strip().lower()
        if not transcript or transcript == "silence":
            return "idle", max(0.2, raw_confidence)

        tokens = set(self._TOKEN_PATTERN.findall(transcript))
        if not tokens:
            return "assist", max(0.55, raw_confidence)

        best_intent = "assist"
        best_score = 0.0
        for intent, keywords in self._INTENT_KEYWORDS.items():
            score = sum(weight for token, weight in keywords.items() if token in tokens)
            if score > best_score:
                best_score = score
                best_intent = intent

        if best_score <= 0.0:
            return "assist", max(0.55, raw_confidence)

        confidence = min(0.35 + best_score * 0.15, 0.9)
        confidence = max(confidence, raw_confidence)
        confidence = max(confidence, 0.55)
        return best_intent, confidence

    def _intent_from_context(self) -> tuple[str, float]:
        if self._recent_transcript():
            return "idle", 0.3
        if "speech_detected" in self._context_tags:
            return "idle", 0.3
        if "high_load" in self._context_tags:
            return "performance_check", 0.45
        if "low_memory" in self._context_tags:
            return "performance_check", 0.45
        if "active_input" in self._context_tags:
            return "do_not_disturb", 0.45
        if "idle_input" in self._context_tags and self._last_transcript:
            return "summary", 0.45
        return "idle", 0.3

    def _intent_from_emotion(self) -> tuple[str, float]:
        if self._last_emotion in {"tired", "calm"}:
            return "wellbeing", 0.55
        if self._last_emotion in {"excited", "curious"}:
            return "assist", 0.5
        return "idle", 0.3

    def _recent_transcript(self) -> bool:
        if not self._last_transcript_time:
            return False
        return time.monotonic() - self._last_transcript_time < self._recent_transcript_window

    def _silence_timeout_elapsed(self) -> bool:
        if not self._last_transcript_time:
            return False
        return time.monotonic() - self._last_transcript_time > self._silence_timeout_seconds
