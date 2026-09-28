"""Tool schemas (Pydantic) and handlers exposed to the agent for tool use.

Every tool input model requires a `reasoning` field so the agent must always explain
itself, and every payload is validated before it ever reaches the `World`, catching
hallucinated fields/types instead of causing a silent bad state change.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from simulator.models import Location
from simulator.world import World


class GetFleetStatusInput(BaseModel):
    """No arguments — returns the full current robots/tasks/events snapshot."""


class AssignTaskInput(BaseModel):
    """Assign an idle robot to a pending task."""

    robot_id: str
    task_id: str
    reasoning: str = Field(..., description="Why this robot/task pairing was chosen over alternatives.")


class RerouteRobotInput(BaseModel):
    """Override a robot's current path with a new list of waypoints."""

    robot_id: str
    new_path: list[Location] = Field(..., description="Ordered list of grid waypoints to follow.")
    reasoning: str = Field(..., description="Why the reroute is necessary.")


class RecallToChargeInput(BaseModel):
    """Send a robot to the nearest charging station, abandoning any active task."""

    robot_id: str
    reasoning: str = Field(..., description="Why the robot needs to charge now.")


class EscalateTaskInput(BaseModel):
    """Flag a task as unfulfillable in time, surfacing it to a human for review."""

    task_id: str
    reasoning: str = Field(..., description="Why this task cannot be completed as scheduled.")


class SimulateScenarioInput(BaseModel):
    """Run planning logic over a hypothetical change without committing it to the world."""

    hypothetical_change: str = Field(..., description="Plain-language description of the what-if.")
    reasoning: str = Field(..., description="What question this simulation is meant to answer.")


TOOL_SCHEMAS: list[dict] = [
    {
        "name": "get_fleet_status",
        "description": "Fetch the current robots, tasks, and recent events. Read-only.",
        "input_schema": GetFleetStatusInput.model_json_schema(),
    },
    {
        "name": "assign_task",
        "description": "Assign an idle robot to a pending task. Only valid on idle robots.",
        "input_schema": AssignTaskInput.model_json_schema(),
    },
    {
        "name": "reroute_robot",
        "description": "Override a robot's current path with a new list of waypoints.",
        "input_schema": RerouteRobotInput.model_json_schema(),
    },
    {
        "name": "recall_to_charge",
        "description": "Send a robot to the nearest charging node. Costly if it has an active task.",
        "input_schema": RecallToChargeInput.model_json_schema(),
    },
    {
        "name": "escalate_task",
        "description": "Flag a task that cannot be fulfilled in time; surfaces it to a human.",
        "input_schema": EscalateTaskInput.model_json_schema(),
    },
    {
        "name": "simulate_scenario",
        "description": "Run planning logic over a hypothetical change without committing it.",
        "input_schema": SimulateScenarioInput.model_json_schema(),
    },
]

# Actions that must be held for human approval rather than applied immediately.
APPROVAL_REQUIRED_ACTIONS = {"recall_to_charge", "escalate_task"}


class ToolHandlers:
    """Executes validated tool-call payloads against a `World` instance."""

    def __init__(self, world: World) -> None:
        self.world = world

    def get_fleet_status(self, payload: GetFleetStatusInput) -> dict:
        return self.world.get_snapshot()

    def assign_task(self, payload: AssignTaskInput) -> dict:
        self.world.assign_task(payload.robot_id, payload.task_id)
        return {"status": "assigned", "robot_id": payload.robot_id, "task_id": payload.task_id}

    def reroute_robot(self, payload: RerouteRobotInput) -> dict:
        self.world.reroute_robot(payload.robot_id, payload.new_path)
        return {"status": "rerouted", "robot_id": payload.robot_id}

    def recall_to_charge(self, payload: RecallToChargeInput) -> dict:
        self.world.recall_to_charge(payload.robot_id)
        return {"status": "charging", "robot_id": payload.robot_id}

    def escalate_task(self, payload: EscalateTaskInput) -> dict:
        self.world.escalate_task(payload.task_id)
        return {"status": "escalated", "task_id": payload.task_id}

    def simulate_scenario(self, payload: SimulateScenarioInput) -> dict:
        """Read-only: summarizes fleet capacity without mutating world state."""
        idle_robots = [r for r in self.world.robots.values() if r.status == "idle"]
        pending_tasks = [t for t in self.world.tasks.values() if t.status == "pending"]
        return {
            "hypothetical_change": payload.hypothetical_change,
            "idle_robot_count": len(idle_robots),
            "pending_task_count": len(pending_tasks),
            "note": "no world state was modified",
        }


INPUT_MODELS: dict[str, type[BaseModel]] = {
    "get_fleet_status": GetFleetStatusInput,
    "assign_task": AssignTaskInput,
    "reroute_robot": RerouteRobotInput,
    "recall_to_charge": RecallToChargeInput,
    "escalate_task": EscalateTaskInput,
    "simulate_scenario": SimulateScenarioInput,
}
