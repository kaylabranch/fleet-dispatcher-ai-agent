"""Tests for `agent/tools.py` handlers — mock tool-call payloads, assert on world state."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.tools import (
    AssignTaskInput,
    EscalateTaskInput,
    RecallToChargeInput,
    ToolHandlers,
)
from simulator.world import World


def test_assign_task_handler_updates_world(sample_world: World) -> None:
    handlers = ToolHandlers(sample_world)
    payload = AssignTaskInput(robot_id="r1", task_id="t1", reasoning="r1 is idle and closest")
    result = handlers.assign_task(payload)
    assert result["status"] == "assigned"
    assert sample_world.robots["r1"].status == "en_route"


def test_assign_task_handler_raises_on_broken_robot(sample_world: World) -> None:
    handlers = ToolHandlers(sample_world)
    payload = AssignTaskInput(robot_id="r2", task_id="t1", reasoning="attempted misuse")
    with pytest.raises(ValueError):
        handlers.assign_task(payload)


def test_assign_task_input_requires_reasoning() -> None:
    with pytest.raises(ValidationError):
        AssignTaskInput(robot_id="r1", task_id="t1")  # missing reasoning


def test_recall_to_charge_handler(sample_world: World) -> None:
    handlers = ToolHandlers(sample_world)
    handlers.assign_task(AssignTaskInput(robot_id="r1", task_id="t1", reasoning="setup"))
    handlers.recall_to_charge(RecallToChargeInput(robot_id="r1", reasoning="battery low"))
    assert sample_world.robots["r1"].status == "charging"


def test_escalate_task_handler(sample_world: World) -> None:
    handlers = ToolHandlers(sample_world)
    handlers.escalate_task(EscalateTaskInput(task_id="t1", reasoning="deadline already passed"))
    assert sample_world.tasks["t1"].status == "failed"


def test_simulate_scenario_does_not_mutate_world(sample_world: World) -> None:
    from agent.tools import SimulateScenarioInput

    handlers = ToolHandlers(sample_world)
    before = sample_world.tasks["t1"].status
    handlers.simulate_scenario(
        SimulateScenarioInput(hypothetical_change="what if r1 went offline?", reasoning="query")
    )
    assert sample_world.tasks["t1"].status == before
