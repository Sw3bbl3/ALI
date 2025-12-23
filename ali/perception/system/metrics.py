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

    Integrates CPU, memory, disk, battery, and network readings when available.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.perception.system")

    def _read_meminfo(self) -> Tuple[float, float, float]:
        meminfo: Dict[str, float] = {}
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as handle:
                for line in handle:
                    key, value = line.split(":", maxsplit=1)
                    meminfo[key.strip()] = float(value.strip().split()[0])
        except FileNotFoundError:
            placeholder_total = 8192.0
            placeholder_used = 2048.0
            placeholder_available = placeholder_total - placeholder_used
            return placeholder_total, placeholder_used, placeholder_available
        total_kb = meminfo.get("MemTotal", 0.0)
        if "MemAvailable" in meminfo:
            available_kb = meminfo["MemAvailable"]
        else:
            available_kb = meminfo.get("MemFree", 0.0) + meminfo.get("Buffers", 0.0) + meminfo.get("Cached", 0.0)
        used_kb = max(total_kb - available_kb, 0.0)
        return total_kb / 1024, used_kb / 1024, available_kb / 1024

    def _read_uptime(self) -> float:
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as handle:
                return float(handle.read().split()[0])
        except FileNotFoundError:
            return 0.0

    def _read_load_average(self) -> Tuple[float, float, float]:
        if not hasattr(os, "getloadavg"):
            return 0.0, 0.0, 0.0
        try:
            return os.getloadavg()
        except OSError:
            return 0.0, 0.0, 0.0

    def _read_network(self) -> Dict[str, Dict[str, float]]:
        stats: Dict[str, Dict[str, float]] = {}
        try:
            with open("/proc/net/dev", "r", encoding="utf-8") as handle:
                for line in handle:
                    if ":" not in line:
                        continue
                    iface, data = line.split(":", maxsplit=1)
                    fields = data.split()
                    if len(fields) < 16:
                        continue
                    stats[iface.strip()] = {
                        "rx_bytes": float(fields[0]),
                        "tx_bytes": float(fields[8]),
                    }
        except FileNotFoundError:
            return {}
        return stats

    def _read_battery(self) -> Dict[str, float]:
        power_path = "/sys/class/power_supply"
        if not os.path.isdir(power_path):
            return {}
        for entry in os.listdir(power_path):
            if not entry.startswith("BAT"):
                continue
            capacity_path = os.path.join(power_path, entry, "capacity")
            status_path = os.path.join(power_path, entry, "status")
            try:
                with open(capacity_path, "r", encoding="utf-8") as handle:
                    capacity = float(handle.read().strip())
                with open(status_path, "r", encoding="utf-8") as handle:
                    status = handle.read().strip().lower()
            except (FileNotFoundError, ValueError):
                continue
            return {"capacity": capacity, "status": status}
        return {}

    async def run(self) -> None:
        """Perception loop placeholder."""
        while True:
            await asyncio.sleep(4)
            total_mem_mb, used_mem_mb, available_mem_mb = self._read_meminfo()
            load_1, load_5, load_15 = self._read_load_average()
            disk_total, disk_used, disk_free = shutil.disk_usage(os.path.abspath(os.sep))
            network = self._read_network()
            battery = self._read_battery()
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
                    "network": network,
                    "battery": battery,
                    "uptime_seconds": round(self._read_uptime(), 2),
                    "timestamp": time.time(),
                },
                source="perception.system",
            )
            self._logger.debug("Collected system metrics")
            await self._event_bus.publish(event)
