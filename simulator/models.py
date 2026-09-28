"""Core Pydantic data models shared by the simulator, agent, and API layer."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    """A point on the abstract 2D grid the fleet operates on."""

    x: float
    y: float


class Robot(BaseModel):
    """A single delivery/service robot and its current physical state."""

    id: str
    location: Location
    status: Literal["idle", "en_route", "charging", "broken"]
    battery: float = Field(ge=0, le=100)
    current_task_id: Optional[str] = None
    speed: float
    route: list[Location] = Field(default_factory=list)
    last_reported_at: Optional[datetime] = None


class Task(BaseModel):
    """A pickup/dropoff job that must be assigned to a robot."""

    id: str
    pickup: Location
    dropoff: Location
    priority: Literal["low", "normal", "high", "urgent"]
    deadline: Optional[datetime] = None
    status: Literal["pending", "assigned", "in_progress", "completed", "failed"]
    assigned_robot_id: Optional[str] = None


class FleetEvent(BaseModel):
    """A disruption or notable occurrence surfaced to the agent for reasoning."""

    id: str
    type: Literal[
        "breakdown",
        "low_battery",
        "blocked_route",
        "new_urgent_task",
        "delay",
        "sensor_anomaly",
        "deadline_conflict",
        "intervention_conflict",
    ]
    robot_id: Optional[str] = None
    task_id: Optional[str] = None
    timestamp: datetime
    details: str


class Decision(BaseModel):
    """A single tool call the agent made during a cycle, with its justification."""

    action: str
    robot_id: Optional[str] = None
    task_id: Optional[str] = None
    reasoning: str


class DecisionLogEntry(BaseModel):
    """One full agent cycle's worth of decisions and flagged risks."""

    cycle: int
    timestamp: datetime
    decisions: list[Decision] = Field(default_factory=list)
    flagged_risks: list[str] = Field(default_factory=list)


class PendingApproval(BaseModel):
    """An action awaiting human sign-off before being applied to the world."""

    id: str
    action: str
    payload: dict
    reasoning: str
    created_at: datetime
    status: Literal["pending", "approved", "rejected"] = "pending"
