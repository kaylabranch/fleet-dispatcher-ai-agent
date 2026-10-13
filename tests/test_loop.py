"""Tests for `agent/loop.py` — a fake agent client stands in for the live Anthropic call."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.client import ToolCall
from agent.loop import AgentLoop
from simulator.events import EventGenerator
from simulator.world import World


@dataclass
class FakeAgentClient:
    """Returns a pre-scripted list of tool calls instead of hitting the Anthropic API."""

    scripted_calls: list[ToolCall]
    has_responded: bool = field(default=False, init=False)

    def decide(self, system_prompt: str, snapshot: str) -> list[ToolCall]:
        """Return the scripted response once, then end the tool-use exchange."""
        if self.has_responded:
            return []
        self.has_responded = True
        return self.scripted_calls


def _quiet_event_generator() -> EventGenerator:
    return EventGenerator(probabilities={})


def test_run_cycle_applies_assign_task_decision(sample_world: World) -> None:
    fake_client = FakeAgentClient(
        scripted_calls=[
            ToolCall(
                id="call_1",
                name="assign_task",
                input={"robot_id": "r1", "task_id": "t1", "reasoning": "r1 is idle and closest"},
            )
        ]
    )
    loop = AgentLoop(world=sample_world, agent_client=fake_client, event_generator=_quiet_event_generator())

    entry = loop.run_cycle()

    assert sample_world.robots["r1"].status == "en_route"
    assert len(entry.decisions) == 1
    assert entry.decisions[0].action == "assign_task"
    assert entry.flagged_risks == []


def test_run_cycle_flags_invalid_tool_call(sample_world: World) -> None:
    fake_client = FakeAgentClient(
        scripted_calls=[
            ToolCall(id="call_1", name="assign_task", input={"robot_id": "r1"})  # missing required fields
        ]
    )
    loop = AgentLoop(world=sample_world, agent_client=fake_client, event_generator=_quiet_event_generator())

    entry = loop.run_cycle()

    assert entry.decisions == []
    assert len(entry.flagged_risks) == 1


def test_approval_required_action_is_held_not_applied(sample_world: World) -> None:
    fake_client = FakeAgentClient(
        scripted_calls=[
            ToolCall(
                id="call_1",
                name="recall_to_charge",
                input={"robot_id": "r1", "reasoning": "battery critical"},
            )
        ]
    )
    loop = AgentLoop(world=sample_world, agent_client=fake_client, event_generator=_quiet_event_generator())

    loop.run_cycle()

    assert sample_world.robots["r1"].status == "idle"  # not yet applied
    assert "call_1" in loop.pending_approvals


def test_resolve_approval_applies_action_once_approved(sample_world: World) -> None:
    fake_client = FakeAgentClient(
        scripted_calls=[
            ToolCall(
                id="call_1",
                name="recall_to_charge",
                input={"robot_id": "r1", "reasoning": "battery critical"},
            )
        ]
    )
    loop = AgentLoop(world=sample_world, agent_client=fake_client, event_generator=_quiet_event_generator())
    loop.run_cycle()

    loop.resolve_approval("call_1", action="approve")

    assert sample_world.robots["r1"].status == "charging"
    assert "call_1" not in loop.pending_approvals


def test_resolve_approval_discards_rejected_action(sample_world: World) -> None:
    fake_client = FakeAgentClient(
        scripted_calls=[
            ToolCall(
                id="call_1",
                name="recall_to_charge",
                input={"robot_id": "r1", "reasoning": "battery critical"},
            )
        ]
    )
    loop = AgentLoop(world=sample_world, agent_client=fake_client, event_generator=_quiet_event_generator())
    loop.run_cycle()

    loop.resolve_approval("call_1", action="reject")

    assert sample_world.robots["r1"].status == "idle"
    assert "call_1" not in loop.pending_approvals


def test_resolve_approval_can_modify_payload_before_applying(sample_world: World) -> None:
    fake_client = FakeAgentClient(
        scripted_calls=[
            ToolCall(
                id="call_1",
                name="recall_to_charge",
                input={"robot_id": "r1", "reasoning": "battery critical"},
            )
        ]
    )
    loop = AgentLoop(world=sample_world, agent_client=fake_client, event_generator=_quiet_event_generator())
    loop.run_cycle()

    loop.resolve_approval(
        "call_1",
        action="modify",
        modified_payload={"robot_id": "r1", "reasoning": "Supervisor confirmed charging is safest."},
    )

    assert sample_world.robots["r1"].status == "charging"
    assert "call_1" not in loop.pending_approvals
