"""Permission and safety gate for ALI actions."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ActionRequest:
    """Represents a proposed action for approval."""

    action_type: str
    payload: Dict[str, Any]
    source: str


class PermissionGate:
    """Placeholder permission system.

    Provides policy rules, user consent hints, and audit logging.
    """

    def __init__(
        self,
        allowed_actions: Optional[List[str]] = None,
        risk_threshold: float = 0.7,
        cooldown_seconds: float = 20.0,
    ) -> None:
        self._allowed_actions = set(allowed_actions or ["notify", "speak", "os"])
        self._risk_threshold = risk_threshold
        self._cooldown_seconds = cooldown_seconds
        self._last_action_time: Dict[str, float] = {}
        self._audit_log: List[AuditEntry] = []
        self._logger = logging.getLogger("ali.permissions")

    def approve(self, request: ActionRequest) -> bool:
        """Return True if the action is permitted."""
        now = time.monotonic()
        if request.action_type not in self._allowed_actions:
            self._record(request, approved=False, reason="action_not_allowed")
            return False

        last_time = self._last_action_time.get(request.action_type, 0.0)
        if now - last_time < self._cooldown_seconds:
            self._record(request, approved=False, reason="cooldown_active")
            return False

        risk_score = float(request.payload.get("risk", 0.0))
        if risk_score >= self._risk_threshold:
            self._record(request, approved=False, reason="risk_too_high")
            return False

        self._last_action_time[request.action_type] = now
        self._record(request, approved=True, reason="approved")
        return True

    def audit_log(self) -> List["AuditEntry"]:
        """Return a copy of the audit log."""
        return list(self._audit_log)

    def _record(self, request: ActionRequest, approved: bool, reason: str) -> None:
        entry = AuditEntry(
            action_type=request.action_type,
            approved=approved,
            reason=reason,
            source=request.source,
            timestamp=time.time(),
        )
        self._audit_log.append(entry)
        self._logger.info(
            "Permission %s for %s (reason=%s)",
            "approved" if approved else "denied",
            request.action_type,
            reason,
        )


@dataclass
class AuditEntry:
    """Records an action approval decision."""

    action_type: str
    approved: bool
    reason: str
    source: str
    timestamp: float
