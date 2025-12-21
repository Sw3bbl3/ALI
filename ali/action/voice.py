"""Voice output actions for ALI."""

from __future__ import annotations

import logging


class VoiceOutput:
    """Generates spoken responses.

    Provides local text output with basic filtering.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("ali.action.voice")

    def speak(self, text: str) -> None:
        """Speak a text string placeholder."""
        if not text.strip():
            return
        self._logger.info("Voice output: %s", text)
