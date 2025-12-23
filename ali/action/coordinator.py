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
            await self._emit_response(
                event,
                {
                    "response_type": "notify",
                    "title": payload.get("title", "ALI"),
                    "message": payload.get("message", ""),
                },
            )
        elif action_type == "speak":
            text = payload.get("text", "")
            self._voice.speak(text)
            await self._emit_response(event, {"response_type": "speak", "text": text})
        elif action_type == "os":
            self._os_controller.execute(OSAction(name=payload.get("name", ""), payload=payload))

        completed = Event(
            event_type="action.completed",
            payload={"action_type": action_type, "source_event": event.event_id},
            source="action.coordinator",
        )
        await self._event_bus.publish(completed)

    async def _emit_response(self, source_event: Event, payload: Dict[str, Any]) -> None:
        if not payload:
            return
        await self._event_bus.publish(
            Event(
                event_type="ali.response",
                payload=payload | {"source_event": source_event.event_id},
                source="action.coordinator",
            )
        )
