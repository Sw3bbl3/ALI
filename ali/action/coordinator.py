"""Action coordinator for ALI."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ali.action.notify import Notification, Notifier
from ali.action.os_control import OSAction, OSController
from ali.action.voice import VoiceOutput
from ali.core.event_bus import Event, EventBus


class ActionCoordinator:
    """Dispatches approved actions to concrete executors."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._notifier = Notifier()
        self._os_controller = OSController()
        self._voice = VoiceOutput()
        self._logger = logging.getLogger("ali.action")

    async def handle(self, event: Event) -> None:
        """Handle action requests and execute them."""
        if event.event_type != "action.requested":
            return

        action_type = event.payload.get("action_type")
        payload: Dict[str, Any] = event.payload.get("payload", {})
        self._logger.info("Executing action %s", action_type)

        if action_type == "notify":
            self._notifier.send(Notification(title=payload.get("title", "ALI"), message=payload.get("message", "")))
        elif action_type == "speak":
            self._voice.speak(payload.get("text", ""))
        elif action_type == "os":
            self._os_controller.execute(OSAction(name=payload.get("name", ""), payload=payload))

        completed = Event(
            event_type="action.completed",
            payload={"action_type": action_type, "source_event": event.event_id},
            source="action.coordinator",
        )
        await self._event_bus.publish(completed)
