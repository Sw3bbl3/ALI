"""Context tagging module."""

from __future__ import annotations

from ali.core.event_bus import Event


class ContextTagger:
    """Adds semantic context tags to events.

    TODO: Integrate context graph and user habit signals.
    """

    async def handle(self, event: Event) -> None:
        """Process an event and enrich with tags."""
        _ = event
        # Placeholder logic only.
