"""Speech interpretation module."""

from __future__ import annotations

from ali.core.event_bus import Event


class SpeechInterpreter:
    """Converts audio events into text transcripts.

    TODO: Integrate local speech-to-text model.
    """

    async def handle(self, event: Event) -> None:
        """Process an audio event and emit a transcript."""
        _ = event
        # Placeholder logic only.
