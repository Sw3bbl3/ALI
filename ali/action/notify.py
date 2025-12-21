"""Notification actions for ALI."""

from __future__ import annotations

import logging
from dataclasses import dataclass


@dataclass
class Notification:
    """Represents a user notification."""

    title: str
    message: str


class Notifier:
    """Delivers notifications to the user.

    TODO: Connect to OS notification APIs.
    """

    def send(self, notification: Notification) -> None:
        """Send a notification placeholder."""
        logger = logging.getLogger("ali.action.notify")
        logger.info("Notification: %s - %s", notification.title, notification.message)
