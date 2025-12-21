"""Intent interpretation module."""

from __future__ import annotations

from ali.core.event_bus import Event


class IntentClassifier:
    """Infers user intent probability vectors.

    TODO: Combine signals from multiple modalities.
    """

    async def handle(self, event: Event) -> None:
        """Process an event and update intent state."""
        _ = event
        # Placeholder logic only.
