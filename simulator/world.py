"""The grid world: holds fleet state and advances it one tick at a time."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Optional

from simulator.models import FleetEvent, Location, Robot, Task
from simulator.utils import grid_distance, step_toward

BATTERY_DRAIN_PER_TICK = 2.0
BATTERY_CHARGE_PER_TICK = 15.0
LOW_BATTERY_THRESHOLD = 20.0
CHARGING_STATION = Location(x=0, y=0)


def _now() -> datetime:
    """Return the current timezone-aware timestamp."""
    return datetime.now(timezone.utc)


class World:
    """Mutable simulation state: robots, tasks, and the running event log."""

    def __init__(
        self,
        robots: dict[str, Robot],
        tasks: dict[str, Task],
        events: list[FleetEvent],
        disruption_probabilities: Optional[dict[str, float]] = None,
    ) -> None:
        self.robots = robots
        self.tasks = tasks
        self.events = events
        self.disruption_probabilities = disruption_probabilities or {}
        self.cycle = 0
        self.blocked_robot_ids: set[str] = set()
        self.unavailable_robot_ids: set[str] = set()
        self.untrusted_robot_ids: set[str] = set()
        self.tasks_requiring_escalation: set[str] = set()

    @classmethod
    def from_scenario(cls, scenario_path: str | Path) -> "World":
        """Build a `World` from a scenario JSON fixture under `data/scenarios/`."""
        data = json.loads(Path(scenario_path).read_text())
        robots = {r["id"]: Robot(**r) for r in data.get("robots", [])}
        tasks = {t["id"]: Task(**t) for t in data.get("tasks", [])}
        events = [FleetEvent(**e) for e in data.get("events", [])]
        return cls(
            robots=robots,
            tasks=tasks,
            events=events,
            disruption_probabilities=data.get("disruption_probabilities", {}),
        )

    def get_snapshot(self, recent_events: int = 10) -> dict:
        """Serialize the current world state for inclusion in an agent prompt."""
        return {
            "cycle": self.cycle,
            "timestamp": _now().isoformat(),
            "robots": [r.model_dump(mode="json") for r in self.robots.values()],
            "tasks": [t.model_dump(mode="json") for t in self.tasks.values()],
            "recent_events": [e.model_dump(mode="json") for e in self.events[-recent_events:]],
            "dispatch_constraints": {
                "blocked_robot_ids": sorted(self.blocked_robot_ids),
                "unavailable_robot_ids": sorted(self.unavailable_robot_ids),
                "untrusted_robot_ids": sorted(self.untrusted_robot_ids),
                "tasks_requiring_escalation": sorted(self.tasks_requiring_escalation),
            },
        }

    def tick(self) -> None:
        """Advance the world by one cycle: move robots, drain/charge battery, complete tasks."""
        self.cycle += 1
        for robot in self.robots.values():
            if robot.status == "en_route" and robot.current_task_id:
                self._advance_robot(robot)
            elif robot.status == "charging":
                self._charge_robot(robot)
            elif robot.status in ("idle",):
                robot.battery = max(0.0, robot.battery - BATTERY_DRAIN_PER_TICK * 0.1)
            robot.last_reported_at = _now()

    def _advance_robot(self, robot: Robot) -> None:
        if robot.id in self.blocked_robot_ids:
            return

        task = self.tasks.get(robot.current_task_id or "")
        if task is None:
            robot.status = "idle"
            robot.current_task_id = None
            robot.route.clear()
            return

        target = robot.route[0] if robot.route else (
            task.dropoff if task.status == "in_progress" else task.pickup
        )
        robot.location = step_toward(robot.location, target, robot.speed)
        robot.battery = max(0.0, robot.battery - BATTERY_DRAIN_PER_TICK)

        if grid_distance(robot.location, target) < 1e-6:
            if robot.route:
                robot.route.pop(0)
                return
            if task.status == "assigned":
                task.status = "in_progress"
            elif task.status == "in_progress":
                task.status = "completed"
                robot.status = "idle"
                robot.current_task_id = None

    def _charge_robot(self, robot: Robot) -> None:
        robot.battery = min(100.0, robot.battery + BATTERY_CHARGE_PER_TICK)
        if grid_distance(robot.location, CHARGING_STATION) > 1e-6:
            robot.location = step_toward(robot.location, CHARGING_STATION, robot.speed)
        elif robot.battery >= 100.0:
            robot.status = "idle"

    # --- mutation methods used by agent tool handlers ---

    def assign_task(self, robot_id: str, task_id: str) -> None:
        """Assign an idle robot to a pending task."""
        robot = self._require_robot(robot_id)
        task = self._require_task(task_id)
        if robot.status != "idle":
            raise ValueError(f"Robot {robot_id} is not idle (status={robot.status})")
        if robot_id in self.unavailable_robot_ids:
            raise ValueError(f"Robot {robot_id} is unavailable due to an intervention")
        if robot_id in self.untrusted_robot_ids:
            raise ValueError(f"Robot {robot_id} has an untrusted location report")
        if task.status != "pending":
            raise ValueError(f"Task {task_id} is not pending (status={task.status})")
        if task_id in self.tasks_requiring_escalation:
            raise ValueError(f"Task {task_id} requires escalation before assignment")
        if task.deadline is not None and task.deadline <= _now():
            raise ValueError(f"Task {task_id} has an expired deadline")
        required_battery = self._required_battery_for_task(robot, task)
        if robot.battery < required_battery:
            raise ValueError(
                f"Robot {robot_id} has insufficient battery ({robot.battery:.1f} < {required_battery:.1f})"
            )
        robot.status = "en_route"
        robot.current_task_id = task_id
        task.status = "assigned"
        task.assigned_robot_id = robot_id

    def reroute_robot(self, robot_id: str, new_path: list[Location | dict[str, float]]) -> None:
        """Replace a robot's route with validated waypoints without teleporting it."""
        robot = self._require_robot(robot_id)
        if not new_path:
            raise ValueError("new_path must contain at least one waypoint")
        robot.route = [
            waypoint if isinstance(waypoint, Location) else Location.model_validate(waypoint)
            for waypoint in new_path
        ]
        self.blocked_robot_ids.discard(robot_id)

    def recall_to_charge(self, robot_id: str) -> None:
        """Send a robot to the charging station, freeing its current task if any."""
        robot = self._require_robot(robot_id)
        if robot.current_task_id:
            task = self.tasks.get(robot.current_task_id)
            if task is not None:
                task.status = "pending"
                task.assigned_robot_id = None
        robot.current_task_id = None
        robot.route.clear()
        self.blocked_robot_ids.discard(robot_id)
        robot.status = "charging"

    def escalate_task(self, task_id: str) -> None:
        """Mark a task as failed and surface it for human review."""
        task = self._require_task(task_id)
        if task.assigned_robot_id:
            robot = self.robots.get(task.assigned_robot_id)
            if robot is not None:
                robot.current_task_id = None
                robot.route.clear()
                robot.status = "idle"
        task.assigned_robot_id = None
        task.status = "failed"
        self.tasks_requiring_escalation.discard(task_id)

    def apply_disruption(self, category: str, robot_id: str | None, task_id: str | None) -> str | None:
        """Apply a generated disruption and return a task ID created by the disruption, if any."""
        if category == "breakdown" and robot_id:
            robot = self._require_robot(robot_id)
            self._release_task(robot)
            robot.route.clear()
            robot.speed = 0
            robot.status = "broken"
        elif category == "low_battery" and robot_id:
            robot = self._require_robot(robot_id)
            robot.battery = min(robot.battery, LOW_BATTERY_THRESHOLD - 1)
        elif category == "blocked_route" and robot_id:
            self.blocked_robot_ids.add(robot_id)
        elif category == "new_urgent_task":
            return self._add_urgent_task()
        elif category == "delay" and robot_id:
            robot = self._require_robot(robot_id)
            robot.speed = max(robot.speed * 0.4, 0.1)
        elif category == "sensor_anomaly" and robot_id:
            self.untrusted_robot_ids.add(robot_id)
        elif category == "deadline_conflict" and task_id:
            self.tasks_requiring_escalation.add(task_id)
        elif category == "intervention_conflict" and robot_id:
            self.unavailable_robot_ids.add(robot_id)
        return None

    def _required_battery_for_task(self, robot: Robot, task: Task) -> float:
        """Return battery needed to complete a pickup/dropoff trip and return to its start."""
        trip_distance = 2 * (grid_distance(robot.location, task.pickup) + grid_distance(task.pickup, task.dropoff))
        return ceil(trip_distance / robot.speed) * BATTERY_DRAIN_PER_TICK

    def _release_task(self, robot: Robot) -> None:
        """Return a robot's active task to the pending queue before disabling the robot."""
        if robot.current_task_id is None:
            return
        task = self.tasks.get(robot.current_task_id)
        if task is not None and task.status in {"assigned", "in_progress"}:
            task.status = "pending"
            task.assigned_robot_id = None
        robot.current_task_id = None

    def _add_urgent_task(self) -> str:
        """Create and return a pending urgent task for a generated urgent-work event."""
        task_id = f"urgent-{self.cycle}-{len(self.tasks) + 1}"
        while task_id in self.tasks:
            task_id = f"{task_id}-new"
        self.tasks[task_id] = Task(
            id=task_id,
            pickup=Location(x=0, y=0),
            dropoff=Location(x=5, y=5),
            priority="urgent",
            deadline=None,
            status="pending",
        )
        return task_id

    def _require_robot(self, robot_id: str) -> Robot:
        robot = self.robots.get(robot_id)
        if robot is None:
            raise ValueError(f"Unknown robot_id: {robot_id}")
        return robot

    def _require_task(self, task_id: str) -> Task:
        task = self.tasks.get(task_id)
        if task is None:
            raise ValueError(f"Unknown task_id: {task_id}")
        return task
