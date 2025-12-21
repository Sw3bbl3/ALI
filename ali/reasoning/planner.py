"""Planning module for ALI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Plan:
    """Represents a proposed plan of action."""

    goal: str
    steps: Dict[str, Any]


class Planner:
    """Builds plans based on interpreted signals.

    TODO: Add multi-step planning and conflict resolution.
    """

    def create_plan(self, goal: str) -> Plan:
        """Create a placeholder plan for a goal."""
        return Plan(goal=goal, steps={"status": "placeholder"})
