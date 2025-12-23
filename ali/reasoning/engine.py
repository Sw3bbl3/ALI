"""Reasoning engine orchestrating memory, planning, and decisions."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from ali.core.event_bus import Event, EventBus
from ali.core.permissions import ActionRequest, PermissionGate
from ali.reasoning.decision import DecisionEngine
from ali.reasoning.memory import MemoryItem, MemoryStore
from ali.reasoning.planner import Plan, Planner
from ali.reasoning.text_generator import TextContext, TextGenerator


@dataclass
class IntentState:
    """Tracks the latest inferred intent."""

    intent: str
    confidence: float


class ReasoningEngine:
    """Connects interpreted signals to decisions and action requests."""

    def __init__(self, event_bus: EventBus, permission_gate: PermissionGate) -> None:
        self._event_bus = event_bus
        self._permission_gate = permission_gate
        self._memory = MemoryStore()
        self._planner = Planner()
        self._decision_engine = DecisionEngine()
        self._intent: Optional[IntentState] = None
        self._last_action_time = 0.0
        self._cooldown_seconds = 30.0
        self._logger = logging.getLogger("ali.reasoning")
        self._text_generator = TextGenerator()

    async def handle(self, event: Event) -> None:
        """Handle interpreted events and decide on actions."""
        self._memory.add_short_term(MemoryItem(key=event.event_type, payload=event.payload))

        if event.event_type == "intent.updated":
            self._intent = IntentState(
                intent=event.payload.get("intent", "idle"),
                confidence=float(event.payload.get("confidence", 0.0)),
            )

        if not self._intent:
            return

        plan = None
        if self._intent.intent != "idle" and self._intent.confidence >= 0.5:
            plan = self._planner.create_plan(goal=f"Assist with {self._intent.intent}")

        risk = plan.risk if plan else 0.0
        policy_allows = True
        decision = self._decision_engine.decide(
            plan=plan,
            confidence=self._intent.confidence,
            risk=risk,
            policy_allows=policy_allows,
        )
        self._logger.info("Decision: should_act=%s plan=%s", decision.should_act, decision.plan)

        if decision.should_act and decision.plan and self._ready_for_action():
            action_type, payload = self._select_action(decision.plan, event)
            request = ActionRequest(
                action_type=action_type,
                payload=payload | {"risk": risk},
                source="reasoning.engine",
            )
            if self._permission_gate.approve(request):
                action_event = Event(
                    event_type="action.requested",
                    payload={
                        "action_type": request.action_type,
                        "payload": request.payload,
                        "source": request.source,
                    },
                    source="reasoning.engine",
                )
                await self._event_bus.publish(action_event)

    def _ready_for_action(self) -> bool:
        now = time.monotonic()
        if now - self._last_action_time < self._cooldown_seconds:
            return False
        self._last_action_time = now
        return True

    def _select_action(self, plan: Plan, event: Event) -> tuple[str, dict]:
        memory_summary = self._memory.summarize()
        context = TextContext(
            goal=plan.goal,
            memory_summary=memory_summary,
            intent=self._intent.intent if self._intent else "idle",
            emotion=event.payload.get("emotion", "neutral"),
            transcript=event.payload.get("transcript", ""),
            context_tags=event.payload.get("context_tags", []),
        )
        message = self._text_generator.notification(context)
        if "focus" in plan.goal.lower():
            return "notify", {"title": "ALI Focus Plan", "message": message, "source_event": event.event_id}
        if "wellbeing" in plan.goal.lower():
            return "speak", {"text": self._text_generator.speech(context)}
        return "notify", {"title": "ALI Assistance", "message": message, "source_event": event.event_id}
