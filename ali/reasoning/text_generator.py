"""Text generation helpers for ALI reasoning."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict

from ali.models.gemma import GemmaLocalModel

logger = logging.getLogger("ali.reasoning.text")


@dataclass
class TextContext:
    """Context passed into text generation."""

    goal: str
    memory_summary: Dict[str, int]
    salient_memories: list[str]
    intent: str
    emotion: str
    transcript: str
    context_tags: list[str]


class TextGenerator:
    """Generate short assistant messages using a local model when available."""

    def __init__(self) -> None:
        self._use_model = os.getenv("ALI_TEXT_MODEL", "gemma").lower() == "gemma"
        self._model: GemmaLocalModel | None = None
        self._preloaded = False

    def preload(self) -> bool:
        """Warm the text model if enabled."""
        if not self._use_model or self._preloaded:
            return False
        try:
            if not self._model:
                self._model = GemmaLocalModel()
            warmed = self._model.warm()
            self._preloaded = warmed
            return warmed
        except Exception as exc:  # noqa: BLE001 - keep startup resilient
            logger.warning("Failed to preload text model: %s", exc)
            return False

    def notification(self, context: TextContext) -> str:
        """Craft a notification message."""
        if self._use_model:
            generated = self._generate(self._prompt(context))
            if generated:
                cleaned = self._clean_generation(generated, max_words=40)
                if cleaned:
                    return cleaned
        return self._fallback_notification(context)

    async def notification_async(self, context: TextContext) -> str:
        """Craft a notification message without blocking the event loop."""
        if self._use_model:
            generated = await self._generate_async(self._prompt(context))
            if generated:
                cleaned = self._clean_generation(generated, max_words=40)
                if cleaned:
                    return cleaned
        return self._fallback_notification(context)

    def speech(self, context: TextContext) -> str:
        """Craft a spoken message."""
        if self._use_model:
            generated = self._generate(self._speech_prompt(context))
            if generated:
                cleaned = self._clean_generation(generated, max_words=30)
                if cleaned:
                    return cleaned
        return self._fallback_speech(context)

    async def speech_async(self, context: TextContext) -> str:
        """Craft a spoken message without blocking the event loop."""
        if self._use_model:
            generated = await self._generate_async(self._speech_prompt(context))
            if generated:
                cleaned = self._clean_generation(generated, max_words=30)
                if cleaned:
                    return cleaned
        return self._fallback_speech(context)

    def _generate(self, prompt: str) -> str | None:
        try:
            if not self._model:
                self._model = GemmaLocalModel()
            return self._model.generate(prompt, max_new_tokens=80, temperature=0.6)
        except Exception as exc:  # noqa: BLE001 - provide fallback
            logger.warning("Text model unavailable: %s", exc)
            return None

    async def _generate_async(self, prompt: str) -> str | None:
        try:
            if not self._model:
                self._model = GemmaLocalModel()
            return await asyncio.to_thread(
                self._model.generate,
                prompt,
                max_new_tokens=80,
                temperature=0.6,
            )
        except Exception as exc:  # noqa: BLE001 - provide fallback
            logger.warning("Text model unavailable: %s", exc)
            return None

    @staticmethod
    def _clean_generation(text: str, *, max_words: int) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return ""
        prompt_prefixes = (
            "you are ali",
            "goal:",
            "intent:",
            "emotion:",
            "transcript:",
            "context tags:",
            "recent signals:",
            "salient memories:",
        )
        candidate = ""
        for line in lines:
            lowered = line.lower()
            if lowered.startswith(("notification:", "spoken reminder:", "response:", "assistant:")):
                candidate = line.split(":", 1)[1].strip()
                if candidate:
                    break
                continue
            if any(lowered.startswith(prefix) for prefix in prompt_prefixes):
                continue
            candidate = line
            break
        if not candidate:
            return ""
        words = candidate.split()
        if len(words) > max_words:
            candidate = " ".join(words[:max_words]).rstrip(".,;:") + "..."
        return candidate

    @staticmethod
    def _fallback_notification(context: TextContext) -> str:
        intent_phrase = TextGenerator._intent_phrase(context)
        if context.intent == "idle":
            return "I'm standing by if you need anything."
        if context.emotion and context.emotion != "neutral":
            return f"I can help with {intent_phrase}, and I hear you're feeling {context.emotion}."
        return f"I can help with {intent_phrase} whenever you're ready."

    @staticmethod
    def _fallback_speech(context: TextContext) -> str:
        intent_phrase = TextGenerator._intent_phrase(context)
        if context.intent == "idle":
            return "I'm here if you need anything."
        if context.transcript:
            snippet = TextGenerator._shorten_transcript(context.transcript, max_words=6)
            return f"Got it: \"{snippet}.\" What would you like me to do?"
        return f"I'm here to help with {intent_phrase}. What should we tackle first?"

    @staticmethod
    def _intent_phrase(context: TextContext) -> str:
        intent = context.intent.strip().replace("_", " ") if context.intent else ""
        if not intent or intent == "idle":
            return "anything"
        if context.goal.lower().startswith("assist with "):
            goal_phrase = context.goal[12:].strip()
            if goal_phrase:
                intent = goal_phrase
        return intent

    @staticmethod
    def _shorten_transcript(transcript: str, *, max_words: int) -> str:
        words = transcript.strip().split()
        if len(words) <= max_words:
            return transcript.strip()
        return " ".join(words[:max_words]).rstrip(".,;:") + "..."

    @staticmethod
    def _prompt(context: TextContext) -> str:
        return (
            "You are ALI, a local privacy-first assistant. "
            "Write one concise notification (max 40 words).\n"
            f"Goal: {context.goal}\n"
            f"Intent: {context.intent}\n"
            f"Emotion: {context.emotion}\n"
            f"Transcript: {context.transcript}\n"
            f"Context tags: {', '.join(context.context_tags) or 'none'}\n"
            f"Recent signals: {context.memory_summary}\n"
            f"Salient memories: {', '.join(context.salient_memories) or 'none'}\n"
            "Notification:"
        )

    @staticmethod
    def _speech_prompt(context: TextContext) -> str:
        return (
            "You are ALI, speaking aloud in a calm tone. "
            "Respond directly to the user's latest message in one short reply (max 30 words). "
            "Ask one clarifying question if needed.\n"
            f"Goal: {context.goal}\n"
            f"Intent: {context.intent}\n"
            f"Emotion: {context.emotion}\n"
            f"Transcript: {context.transcript}\n"
            f"Context tags: {', '.join(context.context_tags) or 'none'}\n"
            f"Recent signals: {context.memory_summary}\n"
            f"Salient memories: {', '.join(context.salient_memories) or 'none'}\n"
            "Response:"
        )
