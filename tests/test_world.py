"""Tests for `simulator/world.py`: tick logic, assignment, and mutation guards."""

from __future__ import annotations

import pytest

from simulator.world import World


def test_assign_task_moves_robot_en_route(sample_world: World) -> None:
    sample_world.assign_task("r1", "t1")
    robot = sample_world.robots["r1"]
    task = sample_world.tasks["t1"]
    assert robot.status == "en_route"
    assert robot.current_task_id == "t1"
    assert task.status == "assigned"
    assert task.assigned_robot_id == "r1"


def test_assign_task_rejects_non_idle_robot(sample_world: World) -> None:
    with pytest.raises(ValueError):
        sample_world.assign_task("r2", "t1")


def test_assign_task_rejects_non_pending_task(sample_world: World) -> None:
    sample_world.assign_task("r1", "t1")
    sample_world.robots["r1"].status = "idle"  # pretend it freed up
    with pytest.raises(ValueError):
        sample_world.assign_task("r1", "t1")


def test_tick_moves_en_route_robot_toward_pickup(sample_world: World) -> None:
    sample_world.assign_task("r1", "t1")
    start_x = sample_world.robots["r1"].location.x
    sample_world.tick()
    assert sample_world.robots["r1"].location.x > start_x


def test_tick_drains_battery_for_en_route_robot(sample_world: World) -> None:
    sample_world.assign_task("r1", "t1")
    start_battery = sample_world.robots["r1"].battery
    sample_world.tick()
    assert sample_world.robots["r1"].battery < start_battery


def test_task_completes_after_reaching_dropoff(sample_world: World) -> None:
    sample_world.assign_task("r1", "t1")
    for _ in range(20):
        sample_world.tick()
        if sample_world.tasks["t1"].status == "completed":
            break
    assert sample_world.tasks["t1"].status == "completed"
    assert sample_world.robots["r1"].status == "idle"


def test_recall_to_charge_frees_active_task(sample_world: World) -> None:
    sample_world.assign_task("r1", "t1")
    sample_world.recall_to_charge("r1")
    assert sample_world.robots["r1"].status == "charging"
    assert sample_world.robots["r1"].current_task_id is None
    assert sample_world.tasks["t1"].status == "pending"


def test_escalate_task_marks_failed(sample_world: World) -> None:
    sample_world.escalate_task("t1")
    assert sample_world.tasks["t1"].status == "failed"


def test_unknown_robot_raises(sample_world: World) -> None:
    with pytest.raises(ValueError):
        sample_world.assign_task("does-not-exist", "t1")
