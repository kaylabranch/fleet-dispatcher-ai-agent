"""REST endpoints: fleet status, decision history, intervention, and approvals."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from server.schemas import (
    ApprovalDecisionRequest,
    DecisionHistoryResponse,
    FleetStatusResponse,
    InterventionRequest,
    PendingApprovalsResponse,
    QueryRequest,
    SimulationControlRequest,
    SimulationStatusResponse,
)
from agent.tools import SimulateScenarioInput, ToolHandlers
from server.state import get_app_state

router = APIRouter()
logger = logging.getLogger("fleet_dispatch")


@router.get("/simulation", response_model=SimulationStatusResponse)
async def get_simulation_status() -> SimulationStatusResponse:
    """Return whether the simulation is stopped, running, or paused."""
    state = get_app_state()
    return SimulationStatusResponse(
        status=state.status,
        scenario=state.scenario_name,
        cycle=state.loop.world.cycle,
    )


@router.post("/simulation", response_model=SimulationStatusResponse)
async def control_simulation(request: SimulationControlRequest) -> SimulationStatusResponse:
    """Start, pause, stop, or reset the simulation from the dashboard."""
    state = get_app_state()
    logger.info(
        "Simulation control received (action=%s, requested_scenario=%s, current_status=%s, current_cycle=%s)",
        request.action,
        request.scenario,
        state.status,
        state.loop.world.cycle,
    )
    if request.action == "reset":
        try:
            state.reset_simulation(request.scenario)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif request.action == "start":
        if request.scenario and request.scenario != state.scenario_name:
            try:
                state.reset_simulation(request.scenario)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        state.status = "running"
    elif request.action == "pause":
        state.status = "paused"
    elif request.action == "stop":
        state.status = "stopped"
    if state.wake_event is not None:
        state.wake_event.set()
    response = SimulationStatusResponse(
        status=state.status,
        scenario=state.scenario_name,
        cycle=state.loop.world.cycle,
    )
    await state.connection_manager.broadcast(
        {
            "fleet": state.loop.world.get_snapshot(),
            "decision": None,
            "approvals": list(state.loop.pending_approvals.values()),
            "status": state.status,
            "scenario": state.scenario_name,
            "error": state.last_error,
        }
    )
    logger.info(
        "Simulation control applied (status=%s, scenario=%s, cycle=%s)",
        state.status,
        state.scenario_name,
        state.loop.world.cycle,
    )
    return response


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
    logger.info("Intervention queued (message_length=%s, simulation_status=%s)", len(request.message), state.status)
    return {"status": "queued"}


@router.post("/approvals/{approval_id}", status_code=200)
async def post_approval_decision(approval_id: str, request: ApprovalDecisionRequest) -> dict:
    """Approve, reject, or modify a held agent action."""
    state = get_app_state()
    logger.info("Approval response received (approval_id=%s, action=%s)", approval_id, request.action)
    try:
        state.loop.resolve_approval(
            approval_id,
            action=request.action,
            modified_payload=request.payload,
        )
    except ValueError as exc:
        logger.warning("Approval response rejected (approval_id=%s, error=%s)", approval_id, exc)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    logger.info("Approval response applied (approval_id=%s, action=%s)", approval_id, request.action)
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
