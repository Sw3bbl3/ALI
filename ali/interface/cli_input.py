"""CLI input interface for ALI."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Iterable

from ali.core.event_bus import Event, EventBus
from ali.core.permissions import ActionRequest, PermissionGate
from ali.models.gemma import GemmaLocalModel

SYSTEM_PROMPT = """You are ALI (Autonomous Local Intelligence), a privacy-first, local-only assistant.
You operate inside an event-driven system with these layers:

- Perception: emits events (e.g., system.metrics, speech.transcript).
- Interpretation: derives intent, emotion, and context tags from events.
- Reasoning: decides when to act and prepares action requests.
- Action: executes tools such as notifications or speech output.

You do NOT have network access. You do NOT execute tools directly.

Available tools (request via TOOL lines only when needed):
- notify: send a user notification. Payload fields: {"title": str, "message": str}
- speak: speak aloud. Payload fields: {"text": str}
- os: execute a local OS action. Payload fields: {"name": str, ...}

To request a tool, append a single line with:
TOOL: <tool_name> <json_payload>

Example:
TOOL: notify {"title": "ALI", "message": "All systems nominal."}

You will be given a Recent events section. Use it as context, and ask the user for clarification
if you need more specifics. Keep responses concise and helpful.
"""


class CliInputMonitor:
    """Reads user input from the CLI and forwards it to ALI."""

    def __init__(self, event_bus: EventBus, permission_gate: PermissionGate) -> None:
        self._event_bus = event_bus
        self._permission_gate = permission_gate
        self._logger = logging.getLogger("ali.interface.cli")
        self._model = GemmaLocalModel()

    async def run(self) -> None:
        """Continuously read CLI input and publish events."""
        self._logger.info("CLI ready. Type your message (or 'exit' to quit).")
        while True:
            message = await self._read_input()
            if message is None:
                return
            message = message.strip()
            if not message:
                continue
            if message.lower() in {"exit", "quit"}:
                self._logger.info("CLI exiting.")
                return

            await self._publish_transcript(message)
            response = self._generate_response(message)
            if response:
                print(f"ALI> {response}")
                await self._handle_tool_calls(response)

    async def _read_input(self) -> str | None:
        try:
            return await asyncio.to_thread(input, "You> ")
        except EOFError:
            self._logger.info("CLI input closed.")
            return None

    async def _publish_transcript(self, message: str) -> None:
        event = Event(
            event_type="speech.transcript",
            payload={
                "transcript": message,
                "confidence": 0.9,
                "intent_hints": self._intent_hints(message),
                "source_event": "cli.input",
            },
            source="cli.input",
        )
        await self._event_bus.publish(event)

    def _generate_response(self, message: str) -> str | None:
        recent_events = self._format_recent_events(self._event_bus.recent_events(limit=6))
        prompt = (
            f"{SYSTEM_PROMPT}\n"
            f"Recent events:\n{recent_events}\n\n"
            f"User message:\n{message}\n\n"
            "Assistant:"
        )
        try:
            return self._model.generate(prompt, max_new_tokens=200, temperature=0.5)
        except Exception as exc:  # noqa: BLE001 - fallback to avoid breaking CLI
            self._logger.warning("Model unavailable, skipping response: %s", exc)
            return None

    @staticmethod
    def _intent_hints(message: str) -> list[str]:
        message_lower = message.lower()
        hints = []
        if "status" in message_lower:
            hints.append("status")
        if "break" in message_lower or "remind" in message_lower:
            hints.append("wellbeing")
        if "focus" in message_lower or "schedule" in message_lower:
            hints.append("focus")
        if "summary" in message_lower or "summarize" in message_lower:
            hints.append("summary")
        return hints

    @staticmethod
    def _format_recent_events(events: Iterable[Event]) -> str:
        lines = []
        for event in events:
            payload_preview = {key: event.payload.get(key) for key in list(event.payload)[:4]}
            lines.append(f"- {event.event_type} from {event.source}: {payload_preview}")
        return "\n".join(lines) if lines else "none"

    async def _handle_tool_calls(self, response: str) -> None:
        for line in response.splitlines():
            if not line.strip().startswith("TOOL:"):
                continue
            tool_name, payload = self._parse_tool_call(line)
            if not tool_name:
                continue
            request = ActionRequest(action_type=tool_name, payload=payload, source="cli.input")
            if not self._permission_gate.approve(request):
                self._logger.info("Tool request denied: %s", tool_name)
                continue
            await self._event_bus.publish(
                Event(
                    event_type="action.requested",
                    payload={
                        "action_type": tool_name,
                        "payload": payload,
                        "source": request.source,
                    },
                    source="cli.input",
                )
            )

    def _parse_tool_call(self, line: str) -> tuple[str | None, Dict[str, Any]]:
        try:
            _, remainder = line.split("TOOL:", maxsplit=1)
            remainder = remainder.strip()
            if not remainder:
                return None, {}
            tool_name, json_blob = remainder.split(" ", maxsplit=1)
            payload = json.loads(json_blob)
            if not isinstance(payload, dict):
                raise ValueError("Tool payload must be a JSON object.")
            return tool_name.strip(), payload
        except ValueError as exc:
            self._logger.warning("Invalid tool call '%s': %s", line, exc)
            return None, {}
