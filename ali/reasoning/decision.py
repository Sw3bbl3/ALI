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

    Uses intent probabilities, risk analysis, and policy constraints.
    """

    def decide(
        self,
        plan: Optional[Plan],
        confidence: float,
        risk: float,
        policy_allows: bool,
    ) -> Decision:
        """Return a decision that factors in confidence and risk."""
        if not plan:
            return Decision(should_act=False, plan=None)
        if not policy_allows:
            return Decision(should_act=False, plan=plan)
        should_act = confidence >= 0.55 and risk <= 0.75
        return Decision(should_act=should_act, plan=plan)
