"""Context tagging module."""

from __future__ import annotations

import logging

from ali.core.event_bus import Event, EventBus


class ContextTagger:
    """Adds semantic context tags to events.

    Integrates lightweight context graph and habit tags.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.interpretation.context")

    async def handle(self, event: Event) -> None:
        """Process an event and enrich with tags."""
        tags = [event.event_type.split(".")[0], "local", "telemetry"]
        payload = event.payload
        if event.event_type == "system.metrics":
            load = payload.get("load_avg", [0])[0]
            if load and load > 2.0:
                tags.append("high_load")
            memory = payload.get("memory_mb", {})
            if memory.get("available", 0) < 1024:
                tags.append("low_memory")
        if event.event_type == "input.activity":
            if payload.get("activity") == "typing":
                tags.append("active_input")
            else:
                tags.append("idle_input")
        if event.event_type == "audio.sampled" and payload.get("is_speech"):
            tags.append("speech_detected")
        if event.event_type == "vision.frame" and payload.get("motion_score", 0) > 0.6:
            tags.append("motion_detected")
        summary = ", ".join(sorted(set(tags)))
        interpreted = Event(
            event_type="context.tagged",
            payload={
                "tags": tags,
                "summary": summary,
                "source_event": event.event_id,
            },
            source="interpretation.context",
        )
        self._logger.info("Tagged event %s with %s", event.event_id, tags)
        await self._event_bus.publish(interpreted)
