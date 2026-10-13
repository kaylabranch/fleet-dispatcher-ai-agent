"""FastAPI app: REST routes, WebSocket push, and the background tick loop."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agent.client import describe_agent_failure
from server.routes import router
from server.state import create_app_state, get_app_state

load_dotenv()

TICK_INTERVAL_SECONDS = float(os.environ.get("TICK_INTERVAL_SECONDS", "5"))
logger = logging.getLogger("fleet_dispatch")


async def _tick_forever() -> None:
    """Background task: runs one agent cycle every TICK_INTERVAL_SECONDS and broadcasts state."""
    state = get_app_state()
    while True:
        if state.wake_event is None:
            state.wake_event = asyncio.Event()
        try:
            await asyncio.wait_for(state.wake_event.wait(), timeout=TICK_INTERVAL_SECONDS)
            state.wake_event.clear()
            logger.info("Scheduler woke from control event (status=%s, cycle=%s)", state.status, state.loop.world.cycle)
        except asyncio.TimeoutError:
            logger.info("Scheduler woke from interval (status=%s, cycle=%s)", state.status, state.loop.world.cycle)
        if state.status != "running":
            logger.info("Skipping cycle because simulation status is %s", state.status)
            continue
        try:
            await _run_one_cycle(state)
        except Exception:
            logger.exception("Scheduler cycle failed; scheduler keeps running")


async def _run_one_cycle(state) -> None:
    """Run a single agent cycle and broadcast the result to connected dashboards."""
    cycle_started = time.perf_counter()
    next_cycle = state.loop.world.cycle + 1
    logger.info(
        "Starting simulation cycle %s (scenario=%s, pending_message=%s, connections=%s)",
        next_cycle,
        state.scenario_name,
        bool(state.pending_user_message),
        len(state.connection_manager.active_connections),
    )
    message = state.pending_user_message
    state.pending_user_message = None
    cycle_error: str | None = None
    if state.agent_disabled:
        state.loop.world.tick()
        entry = state.loop.run_fallback_cycle(state.agent_failure_reason)
        cycle_error = state.last_error or f"AI provider unavailable: {state.agent_failure_reason}"
        logger.warning("Cycle %s used local fallback circuit breaker", entry.cycle)
    else:
        try:
            entry = await asyncio.to_thread(
                state.loop.run_cycle,
                pending_user_message=message,
            )
        except Exception as exc:
            logger.exception("Agent cycle failed after simulator tick: %s", exc)
            state.agent_failure_reason = describe_agent_failure(exc)
            cycle_error = f"AI provider unavailable: {state.agent_failure_reason}"
            state.agent_disabled = True
            entry = state.loop.run_fallback_cycle(state.agent_failure_reason)
            logger.error("Cycle %s used local fallback: %s", entry.cycle, cycle_error)
    state.last_error = cycle_error
    snapshot = state.loop.world.get_snapshot()
    logger.info(
        "Cycle %s state after agent: robots=%s, tasks=%s, events=%s",
        entry.cycle,
        _robot_positions(snapshot),
        len(snapshot["tasks"]),
        len(snapshot["recent_events"]),
    )
    logger.info("Broadcasting cycle %s to %s connection(s)", entry.cycle, len(state.connection_manager.active_connections))
    await state.connection_manager.broadcast(
        {
            "fleet": snapshot,
            "decision": entry.model_dump(),
            "approvals": list(state.loop.pending_approvals.values()),
            "status": state.status,
            "scenario": state.scenario_name,
            "error": cycle_error,
        }
    )
    logger.info(
        "Completed simulation cycle %s (decisions=%s, approvals=%s)",
        entry.cycle,
        len(entry.decisions),
        len(state.loop.pending_approvals),
    )
    logger.info("Cycle %s total duration %.3fs", entry.cycle, time.perf_counter() - cycle_started)


def _robot_positions(snapshot: dict) -> str:
    """Format compact robot telemetry for scheduler diagnostics without logging full prompts."""
    return ", ".join(
        f"{robot['id']}=({robot['location']['x']:.2f},{robot['location']['y']:.2f})/{robot['status']}"
        for robot in snapshot["robots"]
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_app_state()
    get_app_state().wake_event = asyncio.Event()
    logger.info(
        "Fleet API started (tick_interval=%.1fs, model=%s, gemini_timeout=%ss, gemini_key_present=%s)",
        TICK_INTERVAL_SECONDS,
        get_app_state().loop.agent_client.model,
        os.environ.get("GEMINI_TIMEOUT_SECONDS", "5"),
        bool(os.environ.get("GEMINI_API_KEY")),
    )
    tick_task = asyncio.create_task(_tick_forever())
    yield
    tick_task.cancel()
    logger.info("Fleet API shutdown requested")


app = FastAPI(title="Fleet Dispatch Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Streams fleet state + decision log updates to connected dashboard clients."""
    state = get_app_state()
    await state.connection_manager.connect(websocket)
    logger.info("WebSocket client connected (connections=%s)", len(state.connection_manager.active_connections))
    await websocket.send_json(
        {
            "fleet": state.loop.world.get_snapshot(),
            "decision": None,
            "approvals": list(state.loop.pending_approvals.values()),
            "status": state.status,
            "scenario": state.scenario_name,
            "error": state.last_error,
        }
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        state.connection_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected (connections=%s)", len(state.connection_manager.active_connections))
