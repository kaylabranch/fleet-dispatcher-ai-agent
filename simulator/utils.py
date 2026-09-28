"""Shared grid/distance math used by both the simulator and the agent's tools."""

from __future__ import annotations

import math

from simulator.models import Location


def grid_distance(a: Location, b: Location) -> float:
    """Return the straight-line (Euclidean) distance between two grid locations."""
    return math.hypot(a.x - b.x, a.y - b.y)


def step_toward(current: Location, target: Location, max_step: float) -> Location:
    """Return a new location moved from `current` toward `target` by at most `max_step`."""
    distance = grid_distance(current, target)
    if distance <= max_step or distance == 0:
        return Location(x=target.x, y=target.y)
    ratio = max_step / distance
    return Location(
        x=current.x + (target.x - current.x) * ratio,
        y=current.y + (target.y - current.y) * ratio,
    )
