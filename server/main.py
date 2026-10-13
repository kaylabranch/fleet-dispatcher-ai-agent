"""FastAPI app: REST routes, WebSocket push, and the background tick loop."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from google.genai import errors
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from server.routes import router
from server.state import create_app_state, get_app_state
from simulator.models import DecisionLogEntry

load_dotenv()

TICK_INTERVAL_SECONDS = float(os.environ.get("TICK_INTERVAL_SECONDS", "5"))


async def _tick_forever() -> None:
    """Background task: runs one agent cycle every TICK_INTERVAL_SECONDS and broadcasts state."""
    state = get_app_state()
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        if state.status != "running":
            continue
        message = state.pending_user_message
        state.pending_user_message = None
        try:
            entry = state.loop.run_cycle(pending_user_message=message)
        except (ValueError, TimeoutError, errors.APIError) as exc:
            entry = DecisionLogEntry(
                cycle=state.loop.world.cycle,
                timestamp=datetime.now(timezone.utc),
                flagged_risks=[f"agent cycle failed: {exc}"],
            )
            state.loop.decision_log.append(entry)
        await state.connection_manager.broadcast(
            {
                "fleet": state.loop.world.get_snapshot(),
                "decision": entry.model_dump(),
                "approvals": list(state.loop.pending_approvals.values()),
                "status": state.status,
                "scenario": state.scenario_name,
            }
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_app_state()
    tick_task = asyncio.create_task(_tick_forever())
    yield
    tick_task.cancel()


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
    await websocket.send_json(
        {
            "fleet": state.loop.world.get_snapshot(),
            "decision": None,
            "approvals": list(state.loop.pending_approvals.values()),
            "status": state.status,
            "scenario": state.scenario_name,
        }
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        state.connection_manager.disconnect(websocket)
