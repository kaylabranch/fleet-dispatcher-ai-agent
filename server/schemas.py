"""Request/response Pydantic models for the REST + WebSocket API surface."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from simulator.models import DecisionLogEntry, FleetEvent, PendingApproval, Robot, Task


class FleetStatusResponse(BaseModel):
    """Full fleet snapshot returned by `GET /fleet` and pushed over the WebSocket."""

    cycle: int
    robots: list[Robot]
    tasks: list[Task]
    recent_events: list[FleetEvent]


class DecisionHistoryResponse(BaseModel):
    """Decision log history returned by `GET /decisions`."""

    entries: list[DecisionLogEntry]


class InterventionRequest(BaseModel):
    """A human-typed message to inject into the agent's next cycle."""

    message: str


class ApprovalDecisionRequest(BaseModel):
    """Approve or reject a held (`pending_approval`) agent action."""

    action: Literal["approve", "reject"]


class PendingApprovalsResponse(BaseModel):
    """Actions currently awaiting human sign-off."""

    approvals: list[PendingApproval]


class QueryRequest(BaseModel):
    """A read-only hypothetical question about current fleet capacity."""

    hypothetical_change: str
