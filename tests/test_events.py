"""Tests for `simulator/events.py`: probability-driven disruption generation."""

from __future__ import annotations

import random

from simulator.events import EventGenerator
from simulator.world import World


def test_zero_probabilities_generate_no_events(sample_world: World) -> None:
    generator = EventGenerator(probabilities={}, rng=random.Random(42))
    events = generator.generate(sample_world)
    assert events == []


def test_certain_probability_always_generates_event(sample_world: World) -> None:
    generator = EventGenerator(probabilities={"breakdown": 1.0}, rng=random.Random(42))
    events = generator.generate(sample_world)
    assert len(events) == 1
    assert events[0].type == "breakdown"


def test_generated_events_are_appended_to_world_log(sample_world: World) -> None:
    generator = EventGenerator(probabilities={"delay": 1.0}, rng=random.Random(1))
    initial_count = len(sample_world.events)
    generator.generate(sample_world)
    assert len(sample_world.events) == initial_count + 1
