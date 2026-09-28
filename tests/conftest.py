"""Shared pytest fixtures for simulator/agent tests."""

from __future__ import annotations

import pytest

from simulator.models import FleetEvent, Location, Robot, Task
from simulator.world import World


@pytest.fixture
def sample_world() -> World:
    robots = {
        "r1": Robot(
            id="r1",
            location=Location(x=0, y=0),
            status="idle",
            battery=100,
            current_task_id=None,
            speed=2,
        ),
        "r2": Robot(
            id="r2",
            location=Location(x=5, y=5),
            status="broken",
            battery=40,
            current_task_id=None,
            speed=0,
        ),
    }
    tasks = {
        "t1": Task(
            id="t1",
            pickup=Location(x=2, y=0),
            dropoff=Location(x=4, y=0),
            priority="normal",
            deadline=None,
            status="pending",
            assigned_robot_id=None,
        )
    }
    events: list[FleetEvent] = []
    return World(robots=robots, tasks=tasks, events=events, disruption_probabilities={})
