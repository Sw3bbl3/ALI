"""Event logging handler for ALI."""

from __future__ import annotations

import json
import logging

from ali.core.event_bus import Event


class EventLogger:
    """Logs all events flowing through the system."""

    def __init__(self) -> None:
        self._logger = logging.getLogger("ali.events")

    async def handle(self, event: Event) -> None:
        """Log the event payload."""
        try:
            payload = json.dumps(event.payload, default=str)
        except (TypeError, ValueError):
            payload = str(event.payload)
        self._logger.info(
            "Event %s [%s] from %s payload=%s",
            event.event_id,
            event.event_type,
            event.source,
            payload,
        )
