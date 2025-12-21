"""Decision module for ALI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ali.reasoning.planner import Plan


@dataclass
class Decision:
    """Represents a decision to act or stay silent."""

    should_act: bool
    plan: Optional[Plan] = None


class DecisionEngine:
    """Determines whether ALI should take action.

    TODO: Use intent probabilities, risk analysis, and policy constraints.
    """

    def decide(self, plan: Optional[Plan]) -> Decision:
        """Return a placeholder decision."""
        return Decision(should_act=plan is not None, plan=plan)
