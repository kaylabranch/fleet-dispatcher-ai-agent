"""FastAPI app: REST routes, WebSocket push, and the background tick loop."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from server.routes import router
from server.state import create_app_state, get_app_state

load_dotenv()

TICK_INTERVAL_SECONDS = float(os.environ.get("TICK_INTERVAL_SECONDS", "5"))


async def _tick_forever() -> None:
    """Background task: runs one agent cycle every TICK_INTERVAL_SECONDS and broadcasts state."""
    state = get_app_state()
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        message = state.pending_user_message
        state.pending_user_message = None
        entry = state.loop.run_cycle(pending_user_message=message)
        await state.connection_manager.broadcast(
            {
                "fleet": state.loop.world.get_snapshot(),
                "decision": entry.model_dump(),
            }
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_app_state()
    tick_task = asyncio.create_task(_tick_forever())
    yield
    tick_task.cancel()


app = FastAPI(title="Fleet Dispatch Agent", lifespan=lifespan)
app.include_router(router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Streams fleet state + decision log updates to connected dashboard clients."""
    state = get_app_state()
    await state.connection_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        state.connection_manager.disconnect(websocket)
