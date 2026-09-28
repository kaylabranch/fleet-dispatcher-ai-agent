"""Executable specifications for the dispatch rules in the design document."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agent.client import ToolCall
from agent.loop import AgentLoop
from agent.tools import EscalateTaskInput, RerouteRobotInput
from simulator.events import EventGenerator
from simulator.models import Location, Robot, Task
from simulator.world import World


@pytest.fixture
def active_world() -> World:
    """Create a world with one robot already traveling to a task."""
    robot = Robot(
        id="r1",
        location=Location(x=0, y=0),
        status="en_route",
        battery=100,
        current_task_id="t1",
        speed=1,
    )
    task = Task(
        id="t1",
        pickup=Location(x=2, y=0),
        dropoff=Location(x=4, y=0),
        priority="normal",
        deadline=None,
        status="assigned",
        assigned_robot_id="r1",
    )
    return World(robots={robot.id: robot}, tasks={task.id: task}, events=[])


def test_assignment_rejects_a_robot_without_round_trip_battery(sample_world: World) -> None:
    """Assignments must enforce the prompt's battery-sufficiency rule at the simulator boundary."""
    sample_world.robots["r1"].battery = 7

    with pytest.raises(ValueError, match="battery"):
        sample_world.assign_task("r1", "t1")


def test_assignment_rejects_an_expired_deadline(sample_world: World) -> None:
    """An already-expired task must be escalated instead of assigned."""
    sample_world.tasks["t1"].deadline = datetime(2000, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="deadline"):
        sample_world.assign_task("r1", "t1")


def test_timestamps_are_validated_as_iso_datetimes() -> None:
    """Malformed robot timestamps must be rejected at the Pydantic boundary."""
    with pytest.raises(ValidationError):
        Robot(
            id="r1",
            location=Location(x=0, y=0),
            status="idle",
            battery=100,
            speed=1,
            last_reported_at="not-a-timestamp",
        )


def test_reroute_requires_typed_location_waypoints() -> None:
    """Reroute inputs must reject waypoints missing either grid coordinate."""
    with pytest.raises(ValidationError):
        RerouteRobotInput(
            robot_id="r1",
            new_path=[{"x": 3}],
            reasoning="Avoid the blocked route.",
        )


def test_reroute_preserves_position_then_follows_every_waypoint(active_world: World) -> None:
    """A reroute must be movement over a path, not an immediate teleport to one waypoint."""
    active_world.reroute_robot(
        "r1",
        [
            {"x": 0, "y": 2},
            {"x": 2, "y": 2},
        ],
    )

    assert active_world.robots["r1"].location == Location(x=0, y=0)
    active_world.tick()
    assert active_world.robots["r1"].location == Location(x=0, y=1)
    active_world.tick()
    assert active_world.robots["r1"].location == Location(x=0, y=2)
    active_world.tick()
    assert active_world.robots["r1"].location == Location(x=1, y=2)


@pytest.mark.parametrize(
    ("category", "expected_state"),
    [
        ("breakdown", "broken"),
        ("low_battery", "low_battery"),
        ("delay", "delayed"),
        ("new_urgent_task", "new_urgent_task"),
        ("deadline_conflict", "requires_escalation"),
        ("intervention_conflict", "intervention_conflict"),
    ],
)
def test_disruptions_change_simulation_state(
    active_world: World, category: str, expected_state: str
) -> None:
    """Every generated disruption must produce its documented stateful consequence."""
    original_speed = active_world.robots["r1"].speed
    original_task_count = len(active_world.tasks)

    EventGenerator(probabilities={category: 1.0}, rng=random.Random(0)).generate(active_world)

    if expected_state == "broken":
        assert active_world.robots["r1"].status == "broken"
    elif expected_state == "low_battery":
        assert active_world.robots["r1"].battery < 20
    elif expected_state == "delayed":
        assert active_world.robots["r1"].speed < original_speed
    elif expected_state == "new_urgent_task":
        assert len(active_world.tasks) == original_task_count + 1
        assert any(task.priority == "urgent" and task.status == "pending" for task in active_world.tasks.values())
    elif expected_state == "requires_escalation":
        assert "t1" in active_world.tasks_requiring_escalation
    else:
        assert "r1" in getattr(active_world, "unavailable_robot_ids", set())


def test_blocked_route_prevents_progress_until_the_robot_is_rerouted(active_world: World) -> None:
    """A route blockage must stop an en-route robot rather than merely appear in the event log."""
    EventGenerator(probabilities={"blocked_route": 1.0}, rng=random.Random(0)).generate(active_world)
    active_world.tick()

    assert active_world.robots["r1"].location == Location(x=0, y=0)


def test_sensor_anomaly_marks_the_robot_location_untrusted(active_world: World) -> None:
    """A suspect sensor report must be represented so dispatch logic cannot trust it blindly."""
    EventGenerator(probabilities={"sensor_anomaly": 1.0}, rng=random.Random(0)).generate(active_world)

    assert "r1" in getattr(active_world, "untrusted_robot_ids", set())


def test_escalate_task_uses_the_required_reasoning_field() -> None:
    """All agent actions, including escalation, must carry the common `reasoning` field."""
    properties = EscalateTaskInput.model_json_schema()["properties"]

    assert "reasoning" in properties


@dataclass
class FollowUpAgentClient:
    """Test client that expects the loop to request a decision after tool results are available."""

    snapshots: list[str] = field(default_factory=list)

    def decide(self, system_prompt: str, snapshot: str) -> list[ToolCall]:
        """Return a status request first, then end the tool-use exchange."""
        self.snapshots.append(snapshot)
        if len(self.snapshots) == 1:
            return [ToolCall(id="status-1", name="get_fleet_status", input={})]
        return []


def test_agent_receives_tool_results_before_its_follow_up_decision(sample_world: World) -> None:
    """Read-only tools must return data to Claude during the same dispatch cycle."""
    client = FollowUpAgentClient()
    loop = AgentLoop(
        world=sample_world,
        agent_client=client,
        event_generator=EventGenerator(probabilities={}),
    )

    loop.run_cycle()

    assert len(client.snapshots) == 2
    assert '"tool_results"' in client.snapshots[1]
