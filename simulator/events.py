"""Parameterized disruption generator: rolls per-category probabilities each tick."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from simulator.models import FleetEvent
from simulator.world import World

DEFAULT_PROBABILITIES: dict[str, float] = {
    "breakdown": 0.0,
    "low_battery": 0.0,
    "blocked_route": 0.0,
    "new_urgent_task": 0.0,
    "delay": 0.0,
    "sensor_anomaly": 0.0,
    "deadline_conflict": 0.0,
    "intervention_conflict": 0.0,
}


def _now() -> datetime:
    """Return the current timezone-aware timestamp."""
    return datetime.now(timezone.utc)


class EventGenerator:
    """Rolls each disruption category's probability every tick and emits `FleetEvent`s."""

    def __init__(self, probabilities: dict[str, float] | None = None, rng: random.Random | None = None) -> None:
        self.probabilities = {**DEFAULT_PROBABILITIES, **(probabilities or {})}
        self.rng = rng or random.Random()

    def generate(self, world: World) -> list[FleetEvent]:
        """Return newly generated events for this tick, based on configured probabilities."""
        new_events: list[FleetEvent] = []
        for category, probability in self.probabilities.items():
            if probability <= 0:
                continue
            if self.rng.random() < probability:
                event = self._build_event(category, world)
                if event is not None:
                    created_task_id = world.apply_disruption(category, event.robot_id, event.task_id)
                    if created_task_id is not None:
                        event.task_id = created_task_id
                    new_events.append(event)
        world.events.extend(new_events)
        return new_events

    def _build_event(self, category: str, world: World) -> FleetEvent | None:
        candidate_robot_ids = list(world.robots.keys())
        candidate_task_ids = list(world.tasks.keys())
        if not candidate_robot_ids and not candidate_task_ids:
            return None

        robot_id = self.rng.choice(candidate_robot_ids) if candidate_robot_ids else None
        task_id = self.rng.choice(candidate_task_ids) if candidate_task_ids else None

        return FleetEvent(
            id=f"e{uuid.uuid4().hex[:8]}",
            type=category,  # type: ignore[arg-type]
            robot_id=robot_id,
            task_id=task_id,
            timestamp=_now(),
            details=f"auto-generated {category} event",
        )
