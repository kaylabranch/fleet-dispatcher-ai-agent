"""System prompt construction and world-state snapshot serialization for the agent."""

from __future__ import annotations

import json
from typing import Optional

from simulator.world import World

SYSTEM_PROMPT = """You are the dispatch agent for a fleet of delivery/service robots operating \
on an abstract grid. Each cycle you receive a snapshot of all robots, tasks, and recent events, \
and must decide what actions to take using the tools available to you.

Rules:
- Always include a `reasoning` string on every tool call explaining why, referencing the \
  specific data (battery levels, distances, deadlines) that drove the decision.
- Only assign tasks to idle robots with sufficient battery for the round trip.
- Do not trust a single anomalous sensor reading blindly; prefer `get_fleet_status` to confirm \
  before acting on a location that is inconsistent with a robot's last known position and speed.
- If a task's deadline has already passed or cannot realistically be met, call `escalate_task` \
  instead of assigning it.
- When multiple urgent tasks compete for one available robot, pick one and explain the tradeoff \
  in your reasoning rather than leaving both unassigned.
- Use `simulate_scenario` for "what if" questions instead of taking a real action.
"""


def build_system_prompt() -> str:
    """Return the fixed system prompt describing the agent's role and decision rules."""
    return SYSTEM_PROMPT


def build_snapshot(world: World, pending_user_message: Optional[str] = None, recent_events: int = 10) -> str:
    """Serialize the world state (+ any pending intervention message) as the user turn."""
    snapshot = world.get_snapshot(recent_events=recent_events)
    payload = {"fleet_snapshot": snapshot}
    if pending_user_message:
        payload["user_message"] = pending_user_message
    return json.dumps(payload, indent=2)
