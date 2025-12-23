"""Text generation helpers for ALI reasoning."""

from __future__ import annotations

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
    intent: str
    emotion: str
    transcript: str
    context_tags: list[str]


class TextGenerator:
    """Generate short assistant messages using a local model when available."""

    def __init__(self) -> None:
        self._use_model = os.getenv("ALI_TEXT_MODEL", "gemma").lower() == "gemma"
        self._model: GemmaLocalModel | None = None

    def notification(self, context: TextContext) -> str:
        """Craft a notification message."""
        if self._use_model:
            generated = self._generate(self._prompt(context))
            if generated:
                cleaned = self._clean_generation(generated, max_words=40)
                if cleaned:
                    return cleaned
        return (
            f"{context.goal}. Recent signals: {context.memory_summary}. "
            f"Intent={context.intent}, emotion={context.emotion}."
        )

    def speech(self, context: TextContext) -> str:
        """Craft a spoken message."""
        if self._use_model:
            generated = self._generate(self._speech_prompt(context))
            if generated:
                cleaned = self._clean_generation(generated, max_words=30)
                if cleaned:
                    return cleaned
        return f"A gentle reminder from ALI about {context.intent}."

    def _generate(self, prompt: str) -> str | None:
        try:
            if not self._model:
                self._model = GemmaLocalModel()
            return self._model.generate(prompt, max_new_tokens=80, temperature=0.6)
        except Exception as exc:  # noqa: BLE001 - provide fallback
            logger.warning("Text model unavailable: %s", exc)
            return None

    @staticmethod
    def _clean_generation(text: str, *, max_words: int) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return ""
        candidate = lines[0]
        if candidate.lower().startswith("notification:"):
            candidate = candidate.split(":", 1)[1].strip()
        words = candidate.split()
        if len(words) > max_words:
            candidate = " ".join(words[:max_words]).rstrip(".,;:") + "..."
        return candidate

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
            "Notification:"
        )

    @staticmethod
    def _speech_prompt(context: TextContext) -> str:
        return (
            "You are ALI, speaking aloud in a calm tone. "
            "Give a short (max 30 words) spoken reminder.\n"
            f"Goal: {context.goal}\n"
            f"Intent: {context.intent}\n"
            f"Emotion: {context.emotion}\n"
            f"Context tags: {', '.join(context.context_tags) or 'none'}\n"
            "Spoken reminder:"
        )
