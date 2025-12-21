"""System metrics perception module."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from typing import Dict, Tuple

from ali.core.event_bus import Event, EventBus


class SystemMetricsCollector:
    """Collects system metrics and emits telemetry events.

    TODO: Integrate CPU, memory, battery, and network readings.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.perception.system")

    def _read_meminfo(self) -> Tuple[float, float, float]:
        meminfo: Dict[str, float] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, value = line.split(":", maxsplit=1)
                meminfo[key.strip()] = float(value.strip().split()[0])
        total_kb = meminfo.get("MemTotal", 0.0)
        available_kb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0.0))
        used_kb = max(total_kb - available_kb, 0.0)
        return total_kb / 1024, used_kb / 1024, available_kb / 1024

    def _read_uptime(self) -> float:
        with open("/proc/uptime", "r", encoding="utf-8") as handle:
            return float(handle.read().split()[0])

    async def run(self) -> None:
        """Perception loop placeholder."""
        while True:
            await asyncio.sleep(4)
            total_mem_mb, used_mem_mb, available_mem_mb = self._read_meminfo()
            load_1, load_5, load_15 = os.getloadavg()
            disk_total, disk_used, disk_free = shutil.disk_usage("/")
            event = Event(
                event_type="system.metrics",
                payload={
                    "status": "ok",
                    "cpu_count": os.cpu_count() or 1,
                    "load_avg": [load_1, load_5, load_15],
                    "memory_mb": {
                        "total": round(total_mem_mb, 2),
                        "used": round(used_mem_mb, 2),
                        "available": round(available_mem_mb, 2),
                    },
                    "disk_gb": {
                        "total": round(disk_total / 1_073_741_824, 2),
                        "used": round(disk_used / 1_073_741_824, 2),
                        "free": round(disk_free / 1_073_741_824, 2),
                    },
                    "uptime_seconds": round(self._read_uptime(), 2),
                    "timestamp": time.time(),
                },
                source="perception.system",
            )
            self._logger.info("Collected system metrics")
            await self._event_bus.publish(event)
