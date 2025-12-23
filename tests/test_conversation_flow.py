import asyncio
import unittest
from unittest.mock import patch

from ali.core.event_bus import Event, EventBus
from ali.interpretation.intent import IntentClassifier
from ali.reasoning.engine import ReasoningEngine
from ali.reasoning.text_generator import TextContext, TextGenerator


class IntentRecorder:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self._signal = asyncio.Event()

    async def handler(self, event: Event) -> None:
        self.events.append(event)
        self._signal.set()

    async def wait_for_count(self, count: int) -> None:
        while len(self.events) < count:
            self._signal.clear()
            await asyncio.wait_for(self._signal.wait(), timeout=1.0)


class ConversationFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.event_bus = EventBus(worker_count=1)
        self.classifier = IntentClassifier(self.event_bus)
        self.recorder = IntentRecorder()
        await self.event_bus.subscribe("intent.updated", self.recorder.handler)

    async def _next_intent(self, event: Event) -> Event:
        start = len(self.recorder.events)
        await self.classifier._process_event(event)
        await self.recorder.wait_for_count(start + 1)
        return self.recorder.events[-1]

    def _speech_for_intent(self, intent: str, transcript: str) -> str:
        context = TextContext(
            goal=ReasoningEngine._goal_for_intent(intent),
            memory_summary={},
            salient_memories=[],
            intent=intent,
            emotion="neutral",
            transcript=transcript,
            context_tags=[],
        )
        generator = TextGenerator()
        return generator._fallback_speech(context)

    async def test_hi_greets_with_conversational_response(self) -> None:
        event = Event(
            event_type="speech.transcript",
            payload={"transcript": "hi", "confidence": 0.9},
            source="cli.input",
        )
        intent_event = await self._next_intent(event)
        self.assertEqual(intent_event.payload["intent"], "greet")
        response = self._speech_for_intent("greet", "hi").lower()
        self.assertNotIn("what would you like me to do", response)
        self.assertFalse(response.endswith("?"))

    async def test_how_are_you_converse_without_command_prompt(self) -> None:
        event = Event(
            event_type="speech.transcript",
            payload={"transcript": "how are you", "confidence": 0.9},
            source="cli.input",
        )
        intent_event = await self._next_intent(event)
        self.assertEqual(intent_event.payload["intent"], "converse")
        response = self._speech_for_intent("converse", "how are you").lower()
        self.assertNotIn("what would you like me to do", response)

    async def test_silence_timeout_returns_to_idle_and_telemetry_does_not_cancel(self) -> None:
        current_time = 1000.0

        def fake_monotonic() -> float:
            return current_time

        with patch("ali.interpretation.intent.time.monotonic", fake_monotonic):
            greet_event = Event(
                event_type="speech.transcript",
                payload={"transcript": "hi", "confidence": 0.9},
                source="cli.input",
            )
            intent_event = await self._next_intent(greet_event)
            self.assertEqual(intent_event.payload["intent"], "greet")

            current_time += 10.0
            telemetry_event = Event(
                event_type="context.tagged",
                payload={"tags": ["telemetry", "idle_input"], "summary": "telemetry"},
                source="interpretation.context",
            )
            intent_event = await self._next_intent(telemetry_event)
            self.assertEqual(intent_event.payload["intent"], "greet")

            current_time += 15.0
            intent_event = await self._next_intent(telemetry_event)
            self.assertEqual(intent_event.payload["intent"], "idle")
