"""Voice output actions for ALI."""

from __future__ import annotations

import logging


class VoiceOutput:
    """Generates spoken responses.

    TODO: Integrate local text-to-speech engine.
    """

    def speak(self, text: str) -> None:
        """Speak a text string placeholder."""
        logger = logging.getLogger("ali.action.voice")
        logger.info("Voice output: %s", text)
