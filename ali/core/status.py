"""Realtime status reporting for ALI."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict

from ali.core.event_bus import Event


@dataclass
class StatusSnapshot:
    """Snapshot of ALI runtime health."""

    uptime_seconds: float
    total_events: int
    events_by_type: Dict[str, int] = field(default_factory=dict)
    last_seen_by_source: Dict[str, float] = field(default_factory=dict)
    last_event_payloads: Dict[str, str] = field(default_factory=dict)


class StatusReporter:
    """Aggregates events and emits periodic status summaries."""

    def __init__(self, interval_seconds: int = 5) -> None:
        self._interval_seconds = interval_seconds
        self._start_time = time.monotonic()
        self._counts: Counter[str] = Counter()
        self._last_seen_by_source: Dict[str, float] = {}
        self._last_payloads: Dict[str, str] = {}
        self._logger = logging.getLogger("ali.status")

    async def handle_event(self, event: Event) -> None:
        """Update status state with the latest event."""
        self._counts[event.event_type] += 1
        self._last_seen_by_source[event.source] = time.monotonic()
        try:
            payload = json.dumps(event.payload, default=str)
        except (TypeError, ValueError):
            payload = str(event.payload)
        self._last_payloads[event.event_type] = payload

    def _snapshot(self) -> StatusSnapshot:
        uptime_seconds = time.monotonic() - self._start_time
        return StatusSnapshot(
            uptime_seconds=uptime_seconds,
            total_events=sum(self._counts.values()),
            events_by_type=dict(self._counts),
            last_seen_by_source=dict(self._last_seen_by_source),
            last_event_payloads=dict(self._last_payloads),
        )

    async def run(self) -> None:
        """Periodically log status summaries."""
        while True:
            await asyncio.sleep(self._interval_seconds)
            snapshot = self._snapshot()
            self._logger.debug(
                "Status | uptime=%.1fs events=%s sources=%s",
                snapshot.uptime_seconds,
                snapshot.events_by_type,
                list(snapshot.last_seen_by_source.keys()),
            )
