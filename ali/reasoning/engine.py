"""Reasoning engine orchestrating memory, planning, and decisions."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

from ali.core.event_bus import Event, EventBus
from ali.core.permissions import ActionRequest, PermissionGate
from ali.reasoning.decision import Decision, DecisionEngine
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
        if os.getenv("ALI_PRELOAD_TEXT_MODEL", "false").lower() in {"1", "true", "yes"}:
            self._text_generator.preload()

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
        cooldown_ready = self._cooldown_ready()
        action: tuple[str, dict] | None = None
        if decision.should_act and decision.plan and cooldown_ready:
            action = await self._select_action(decision.plan, event)

        self._logger.info("Decision: should_act=%s plan=%s", decision.should_act, decision.plan)
        await self._emit_reasoning_trace(decision, plan, event, action, cooldown_ready)

        if action:
            action_type, payload = action
            request = ActionRequest(
                action_type=action_type,
                payload=payload | {"risk": risk},
                source="reasoning.engine",
            )
            if self._permission_gate.approve(request):
                self._mark_action()
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

    async def _emit_reasoning_trace(
        self,
        decision: Decision,
        plan: Plan | None,
        event: Event,
        action: tuple[str, dict] | None,
        cooldown_ready: bool,
    ) -> None:
        plan_steps = plan.steps if plan else []
        payload = {
            "intent": self._intent.intent if self._intent else "idle",
            "confidence": round(self._intent.confidence, 3) if self._intent else 0.0,
            "goal": plan.goal if plan else "idle",
            "plan_steps": plan_steps,
            "risk": round(plan.risk if plan else 0.0, 3),
            "should_act": decision.should_act,
            "cooldown_ready": cooldown_ready,
            "memory_summary": self._memory.summarize(),
            "source_event": event.event_id,
        }
        if action:
            action_type, action_payload = action
            payload["action_type"] = action_type
            payload["action_payload"] = action_payload
        await self._event_bus.publish(
            Event(
                event_type="reasoning.trace",
                payload=payload,
                source="reasoning.engine",
            )
        )

    def _cooldown_ready(self) -> bool:
        now = time.monotonic()
        return now - self._last_action_time >= self._cooldown_seconds

    def _mark_action(self) -> None:
        self._last_action_time = time.monotonic()

    async def _select_action(self, plan: Plan, event: Event) -> tuple[str, dict]:
        memory_summary = self._memory.summarize()
        salient_items = self._memory.recall_salient(limit=3)
        salient_memories = [self._memory.summarize_item(item) for item in salient_items]
        context = TextContext(
            goal=plan.goal,
            memory_summary=memory_summary,
            salient_memories=salient_memories,
            intent=self._intent.intent if self._intent else "idle",
            emotion=event.payload.get("emotion", "neutral"),
            transcript=event.payload.get("transcript", ""),
            context_tags=event.payload.get("context_tags", []),
        )
        if context.transcript:
            speech = await self._text_generator.speech_async(context)
            return "speak", {"text": speech, "source_event": event.event_id}

        message = await self._text_generator.notification_async(context)
        if "focus" in plan.goal.lower():
            return "notify", {"title": "ALI Focus Plan", "message": message, "source_event": event.event_id}
        if "wellbeing" in plan.goal.lower():
            return "notify", {"title": "ALI Wellbeing", "message": message, "source_event": event.event_id}
        if "summary" in plan.goal.lower():
            return "notify", {"title": "ALI Summary", "message": message, "source_event": event.event_id}
        return "notify", {"title": "ALI Assistance", "message": message, "source_event": event.event_id}
