"""Process-wide application state: the shared `World`/`AgentLoop` singleton and connections."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from agent.client import AgentClient
from agent.loop import AgentLoop
from simulator.world import World

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "data" / "scenarios"


@dataclass
class ConnectionManager:
    """Tracks connected WebSocket clients and broadcasts fleet updates to all of them."""

    active_connections: list[WebSocket] = field(default_factory=list)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError, OSError):
                self.disconnect(connection)


@dataclass
class AppState:
    """Holds the single `AgentLoop` instance and cross-request state for the FastAPI app."""

    loop: AgentLoop
    connection_manager: ConnectionManager
    pending_user_message: Optional[str] = None
    status: Literal["stopped", "running", "paused"] = "stopped"
    scenario_name: str = "calm_day"

    def reset_simulation(self, scenario_name: str | None = None) -> None:
        """Replace the current simulation with a fresh world for a selected scenario."""
        selected_scenario = scenario_name or self.scenario_name
        scenario_path = SCENARIOS_DIR / f"{selected_scenario}.json"
        if not scenario_path.is_file():
            raise ValueError(f"Unknown scenario: {selected_scenario}")
        self.loop = AgentLoop(world=World.from_scenario(scenario_path), agent_client=self.loop.agent_client)
        self.scenario_name = selected_scenario
        self.pending_user_message = None
        self.status = "stopped"


_app_state: Optional[AppState] = None


def create_app_state() -> AppState:
    """Build the initial stopped `AppState` with the default dashboard scenario."""
    scenario_name = "calm_day"
    world = World.from_scenario(SCENARIOS_DIR / f"{scenario_name}.json")
    agent_client = AgentClient()
    loop = AgentLoop(world=world, agent_client=agent_client)
    global _app_state
    _app_state = AppState(
        loop=loop,
        connection_manager=ConnectionManager(),
        scenario_name=scenario_name,
    )
    return _app_state


def get_app_state() -> AppState:
    """Return the process-wide `AppState`, creating it on first access."""
    if _app_state is None:
        return create_app_state()
    return _app_state
