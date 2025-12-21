"""Notification actions for ALI."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass


@dataclass
class Notification:
    """Represents a user notification."""

    title: str
    message: str


class Notifier:
    """Delivers notifications to the user.

    Provides in-process notifications with basic deduplication.
    """

    def __init__(self, cooldown_seconds: float = 5.0) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._last_message: str = ""
        self._last_time = 0.0
        self._logger = logging.getLogger("ali.action.notify")

    def send(self, notification: Notification) -> None:
        """Send a notification placeholder."""
        now = time.monotonic()
        if notification.message == self._last_message and now - self._last_time < self._cooldown_seconds:
            self._logger.debug("Skipping duplicate notification")
            return
        self._last_message = notification.message
        self._last_time = now
        self._logger.info("Notification: %s - %s", notification.title, notification.message)
