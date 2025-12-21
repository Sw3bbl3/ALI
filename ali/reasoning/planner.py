"""Planning module for ALI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Plan:
    """Represents a proposed plan of action."""

    goal: str
    steps: List[Dict[str, Any]]
    risk: float = 0.0


class Planner:
    """Builds plans based on interpreted signals.

    Adds multi-step planning and simple conflict resolution.
    """

    def create_plan(self, goal: str) -> Plan:
        """Create a placeholder plan for a goal."""
        steps = self._steps_for_goal(goal)
        risk = self._estimate_risk(steps)
        return Plan(goal=goal, steps=steps, risk=risk)

    def _steps_for_goal(self, goal: str) -> List[Dict[str, Any]]:
        goal_lower = goal.lower()
        if "status" in goal_lower:
            return [
                {"action": "collect_metrics", "detail": "Gather system telemetry"},
                {"action": "summarize", "detail": "Summarize system health"},
                {"action": "notify", "detail": "Send status update"},
            ]
        if "focus" in goal_lower:
            return [
                {"action": "assess_context", "detail": "Check activity and load"},
                {"action": "suggest", "detail": "Recommend focus window"},
                {"action": "notify", "detail": "Deliver focus plan"},
            ]
        if "wellbeing" in goal_lower or "break" in goal_lower:
            return [
                {"action": "assess_fatigue", "detail": "Review activity patterns"},
                {"action": "suggest_break", "detail": "Offer a short break"},
                {"action": "notify", "detail": "Send wellbeing reminder"},
            ]
        if "summary" in goal_lower:
            return [
                {"action": "gather_events", "detail": "Collect recent events"},
                {"action": "summarize", "detail": "Build a quick digest"},
                {"action": "notify", "detail": "Send summary"},
            ]
        return [
            {"action": "observe", "detail": "Monitor signals"},
            {"action": "assist", "detail": "Provide gentle assistance"},
        ]

    def _estimate_risk(self, steps: List[Dict[str, Any]]) -> float:
        risk = 0.2
        for step in steps:
            if step["action"] in {"notify", "suggest", "summarize"}:
                risk += 0.05
            if step["action"] == "collect_metrics":
                risk += 0.1
        return min(risk, 1.0)
