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
    _GREETINGS = {"hi", "hello", "hey"}
    _CONVERSE_PHRASES = {
        "how are you",
        "how's it going",
        "hows it going",
        "what's up",
        "whats up",
        "say something",
    }
    _COMMAND_VERBS = {"open", "run", "show", "do", "execute", "start", "launch"}
    _INTENT_KEYWORDS: dict[str, dict[str, float]] = {
        "greet": {
            "hello": 1.2,
            "hi": 1.1,
            "hey": 1.0,
        },
        "converse": {
            "chat": 0.8,
            "talk": 0.8,
            "how": 0.7,
            "what": 0.5,
            "up": 0.4,
        },
        "command": {
            "open": 1.0,
            "run": 1.0,
            "show": 0.9,
            "do": 0.8,
            "execute": 1.0,
            "start": 0.9,
            "launch": 0.9,
            "help": 0.7,
        },
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
    }

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.interpretation.intent")
        self._context_tags: set[str] = set()
        self._last_emotion: str = "neutral"
        self._last_transcript: str = ""
        self._conversation_duration_seconds = 20.0
        self._conversation_active = False
        self._conversation_expires_at = 0.0
        self._current_intent = "idle"
        self._current_confidence = 0.3
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
        now = time.monotonic()
        if event.event_type == "context.tagged":
            self._context_tags = set(event.payload.get("tags", []))
        if event.event_type == "emotion.detected":
            self._last_emotion = event.payload.get("emotion", "neutral")

        transcript = ""
        intent = self._current_intent
        confidence = self._current_confidence
        reason = "retain"
        is_user_input = self._is_user_input(event)

        if event.event_type == "speech.transcript":
            transcript = event.payload.get("transcript", "")
            if transcript.strip().lower() == "silence":
                is_user_input = False
            raw_confidence = float(event.payload.get("confidence", 0.3))
            if is_user_input:
                intent, confidence = self._intent_from_transcript(transcript, raw_confidence)
                self._last_transcript = transcript
                reason = "user_input"
            else:
                intent, confidence, reason = self._intent_from_telemetry(now)
        elif event.event_type in {"context.tagged", "emotion.detected"}:
            intent, confidence, reason = self._intent_from_telemetry(now)

        if is_user_input:
            if intent in {"greet", "converse"}:
                if not self._conversation_active:
                    self._logger.debug("Entering conversation_mode")
                self._conversation_active = True
                self._conversation_expires_at = now + self._conversation_duration_seconds
            elif self._conversation_active:
                self._logger.debug("Exiting conversation_mode due to user intent change")
                self._conversation_active = False
                self._conversation_expires_at = 0.0

        if intent != self._current_intent:
            self._logger.debug(
                "Intent transition %s -> %s (reason=%s)",
                self._current_intent,
                intent,
                reason,
            )

        self._current_intent = intent
        self._current_confidence = confidence

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

        token_list = self._TOKEN_PATTERN.findall(transcript)
        tokens = set(token_list)
        if not tokens:
            return "converse", max(0.5, raw_confidence)

        if any(phrase in transcript for phrase in self._CONVERSE_PHRASES):
            return "converse", max(0.6, raw_confidence)
        if token_list and token_list[0] in self._GREETINGS and len(token_list) <= 3:
            return "greet", max(0.7, raw_confidence)
        if token_list and (
            token_list[0] in self._COMMAND_VERBS
            or (len(token_list) > 1 and token_list[0] == "please" and token_list[1] in self._COMMAND_VERBS)
        ):
            return "command", max(0.65, raw_confidence)

        best_intent = "converse"
        best_score = 0.0
        for intent, keywords in self._INTENT_KEYWORDS.items():
            score = sum(weight for token, weight in keywords.items() if token in tokens)
            if score > best_score:
                best_score = score
                best_intent = intent

        if best_score <= 0.0:
            if self._COMMAND_VERBS.intersection(tokens):
                return "command", max(0.6, raw_confidence)
            return "converse", max(0.5, raw_confidence)

        confidence = min(0.35 + best_score * 0.15, 0.9)
        confidence = max(confidence, raw_confidence)
        confidence = max(confidence, 0.55)
        return best_intent, confidence

    def _intent_from_telemetry(self, now: float) -> tuple[str, float, str]:
        if self._conversation_active:
            if now >= self._conversation_expires_at:
                self._logger.debug("Exiting conversation_mode after timeout")
                self._conversation_active = False
                self._conversation_expires_at = 0.0
                return "idle", 0.3, "conversation_timeout"
            return self._current_intent, self._current_confidence, "conversation_hold"
        if self._current_intent != "idle":
            return self._current_intent, self._current_confidence, "telemetry_hold"
        return "idle", 0.3, "telemetry_idle"
