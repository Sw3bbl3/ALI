"""OS automation actions for ALI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class OSAction:
    """Represents an OS-level action request."""

    name: str
    payload: Dict[str, Any]


class OSController:
    """Executes OS-level actions.

    Implements safe, reversible automation hooks.
    """

    def __init__(self, allowlist: tuple[str, ...] = ("open_app", "adjust_volume", "toggle_setting")) -> None:
        self._allowlist = set(allowlist)
        self._logger = logging.getLogger("ali.action.os")

    def execute(self, action: OSAction) -> bool:
        """Execute an OS action placeholder."""
        if action.name not in self._allowlist:
            self._logger.warning("Blocked OS action %s", action.name)
            return False
        self._logger.info("OS action executed: %s payload=%s", action.name, action.payload)
        return True
