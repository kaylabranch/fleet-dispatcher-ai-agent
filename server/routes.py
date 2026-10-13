"""REST endpoints: fleet status, decision history, intervention, and approvals."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.schemas import (
    ApprovalDecisionRequest,
    DecisionHistoryResponse,
    FleetStatusResponse,
    InterventionRequest,
    PendingApprovalsResponse,
    QueryRequest,
)
from agent.tools import SimulateScenarioInput, ToolHandlers
from server.state import get_app_state

router = APIRouter()


@router.get("/fleet", response_model=FleetStatusResponse)
async def get_fleet_status() -> FleetStatusResponse:
    """Return the current robots, tasks, and recent events."""
    state = get_app_state()
    snapshot = state.loop.world.get_snapshot()
    return FleetStatusResponse(**snapshot)


@router.get("/decisions", response_model=DecisionHistoryResponse)
async def get_decision_history() -> DecisionHistoryResponse:
    """Return the full agent decision log accumulated so far."""
    state = get_app_state()
    return DecisionHistoryResponse(entries=state.loop.decision_log)


@router.get("/approvals", response_model=PendingApprovalsResponse)
async def get_pending_approvals() -> PendingApprovalsResponse:
    """Return actions currently awaiting human approval."""
    state = get_app_state()
    return PendingApprovalsResponse(approvals=list(state.loop.pending_approvals.values()))


@router.post("/intervene", status_code=202)
async def post_intervention(request: InterventionRequest) -> dict:
    """Queue a human message to be injected into the agent's next cycle."""
    state = get_app_state()
    state.pending_user_message = request.message
    return {"status": "queued"}


@router.post("/approvals/{approval_id}", status_code=200)
async def post_approval_decision(approval_id: str, request: ApprovalDecisionRequest) -> dict:
    """Approve or reject a held agent action."""
    state = get_app_state()
    try:
        state.loop.resolve_approval(approval_id, approve=request.action == "approve")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": request.action}


@router.post("/query")
async def post_query(request: QueryRequest) -> dict:
    """Return a read-only what-if summary without changing simulator state."""
    state = get_app_state()
    payload = SimulateScenarioInput(
        hypothetical_change=request.hypothetical_change,
        reasoning="Human requested a read-only what-if query.",
    )
    return ToolHandlers(state.loop.world).simulate_scenario(payload)
