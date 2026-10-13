"""The observe -> decide -> act -> update cycle tying the agent to the simulator."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Protocol

from pydantic import ValidationError

from agent.client import ToolCall
from agent.prompt import build_snapshot, build_system_prompt
from agent.tools import APPROVAL_REQUIRED_ACTIONS, INPUT_MODELS, ToolHandlers
from simulator.events import EventGenerator
from simulator.models import Decision, DecisionLogEntry, PendingApproval
from simulator.utils import grid_distance
from simulator.world import World
logger = logging.getLogger("fleet_dispatch")
MAX_AGENT_TURNS_PER_CYCLE = 2
LOW_BATTERY_THRESHOLD = 20
# Only these tools return data the model needs to see before deciding; mutating tools do not need a follow-up call.
INFORMATIONAL_TOOLS = {"get_fleet_status", "simulate_scenario"}


class DecidesTools(Protocol):
    """Structural type for anything that can produce tool calls from a snapshot (real client or test double)."""

    def decide(self, system_prompt: str, snapshot: str) -> list[ToolCall]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentLoop:
    """Runs one full dispatch cycle: generate events, ask the agent, apply its decisions."""

    def __init__(self, world: World, agent_client: DecidesTools, event_generator: Optional[EventGenerator] = None) -> None:
        self.world = world
        self.agent_client = agent_client
        self.event_generator = event_generator or EventGenerator(world.disruption_probabilities)
        self.tool_handlers = ToolHandlers(world)
        self.decision_log: list[DecisionLogEntry] = []
        self.pending_approvals: dict[str, PendingApproval] = {}
        self._seen_event_ids: set[str] = set()

    def _needs_agent(self, pending_user_message: Optional[str]) -> bool:
        """Return True only when there is something new for the model to decide, to avoid wasted API calls."""
        new_events = {event.id for event in self.world.events} - self._seen_event_ids
        if pending_user_message or new_events:
            return True
        robots = self.world.robots.values()
        has_idle = any(robot.status == "idle" for robot in robots)
        has_pending_task = any(task.status == "pending" for task in self.world.tasks.values())
        low_battery_idle = any(
            robot.status == "idle" and robot.battery <= LOW_BATTERY_THRESHOLD and not self._has_pending_approval("recall_to_charge", robot.id)
            for robot in robots
        )
        return (has_idle and has_pending_task) or low_battery_idle

    def run_cycle(self, pending_user_message: Optional[str] = None) -> DecisionLogEntry:
        """Execute one observe-decide-act-update cycle and return the resulting log entry."""
        cycle_started = time.perf_counter()
        logger.info("Agent loop started (cycle_before=%s, intervention=%s)", self.world.cycle, bool(pending_user_message))
        self.event_generator.generate(self.world)
        logger.info("Events generated (event_count=%s)", len(self.world.events))
        self.world.tick()
        logger.info("World advanced before agent request (cycle=%s)", self.world.cycle)

        system_prompt = build_system_prompt()
        snapshot = build_snapshot(self.world, pending_user_message=pending_user_message)

        decisions: list[Decision] = []
        flagged_risks: list[str] = []
        needs_agent = self._needs_agent(pending_user_message)
        self._seen_event_ids = {event.id for event in self.world.events}
        if not needs_agent:
            logger.info("Skipping agent call: nothing new to decide (cycle=%s)", self.world.cycle)
            tool_calls: list[ToolCall] = []
        else:
            tool_calls = self.agent_client.decide(system_prompt, snapshot)
        logger.info("Agent returned %s tool call(s) in initial response", len(tool_calls))

        for turn in range(MAX_AGENT_TURNS_PER_CYCLE):
            if not tool_calls:
                break
            tool_results: list[dict] = []
            needs_follow_up = False
            for call in tool_calls:
                logger.info("Applying tool call (name=%s, id=%s)", call.name, call.id)
                try:
                    decision, result = self._apply_tool_call(call)
                    if decision is not None:
                        decisions.append(decision)
                    tool_results.append({"tool_call_id": call.id, "tool_name": call.name, "result": result})
                    needs_follow_up = needs_follow_up or call.name in INFORMATIONAL_TOOLS
                except (ValidationError, ValueError) as exc:
                    message = f"rejected tool call '{call.name}': {exc}"
                    flagged_risks.append(message)
                    tool_results.append({"tool_call_id": call.id, "tool_name": call.name, "error": str(exc)})
                    logger.warning("Tool call rejected (name=%s, error=%s)", call.name, exc)
            if not needs_follow_up or turn == MAX_AGENT_TURNS_PER_CYCLE - 1:
                break
            snapshot = json.dumps(
                {
                    "fleet_snapshot": self.world.get_snapshot(),
                    "tool_results": tool_results,
                },
                indent=2,
            )
            tool_calls = self.agent_client.decide(system_prompt, snapshot)
            logger.info("Agent returned %s follow-up tool call(s) (turn=%s)", len(tool_calls), turn + 2)

        entry = DecisionLogEntry(
            cycle=self.world.cycle,
            timestamp=_now(),
            decisions=decisions,
            flagged_risks=flagged_risks,
        )
        self.decision_log.append(entry)
        logger.info(
            "Agent loop completed (cycle=%s, decisions=%s, risks=%s, duration=%.3fs)",
            entry.cycle,
            len(entry.decisions),
            len(entry.flagged_risks),
            time.perf_counter() - cycle_started,
        )
        return entry

    def run_fallback_cycle(self, reason: str) -> DecisionLogEntry:
        """Apply safe local dispatch decisions when the configured provider is unavailable."""
        decisions: list[Decision] = []
        flagged_risks = [f"Gemini unavailable; local fallback dispatch used: {reason}"]
        for robot in self.world.robots.values():
            if robot.status == "idle" and robot.battery <= 20 and not self._has_pending_approval(
                "recall_to_charge", robot.id
            ):
                decisions.append(
                    self._queue_fallback_approval(
                        action="recall_to_charge",
                        payload={"robot_id": robot.id, "reasoning": "[local fallback] battery is below the safe threshold"},
                        reasoning=f"[local fallback] {robot.id} battery is {robot.battery:.1f}%; supervisor review required before charging",
                    )
                )

        for task in self.world.tasks.values():
            if (
                task.status == "pending"
                and task.deadline is not None
                and task.deadline <= self.world.current_time
                and not self._has_pending_approval("escalate_task", task.id)
            ):
                decisions.append(
                    self._queue_fallback_approval(
                        action="escalate_task",
                        payload={"task_id": task.id, "reasoning": "[local fallback] deadline has passed"},
                        reasoning=f"[local fallback] task {task.id} deadline has passed; supervisor review required",
                    )
                )

        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        pending_tasks = sorted(
            (task for task in self.world.tasks.values() if task.status == "pending"),
            key=lambda task: (priority_order[task.priority], task.deadline is None, task.deadline or self.world.current_time),
        )
        for task in pending_tasks:
            candidates = sorted(
                (robot for robot in self.world.robots.values() if robot.status == "idle"),
                key=lambda robot: grid_distance(robot.location, task.pickup),
            )
            for robot in candidates:
                try:
                    self.world.assign_task(robot.id, task.id)
                except ValueError:
                    continue
                decisions.append(
                    Decision(
                        action="assign_task",
                        robot_id=robot.id,
                        task_id=task.id,
                        reasoning=f"[local fallback] assigned nearest eligible robot; provider unavailable ({reason})",
                    )
                )
                break
        entry = DecisionLogEntry(
            cycle=self.world.cycle,
            timestamp=_now(),
            decisions=decisions,
            flagged_risks=flagged_risks,
        )
        self.decision_log.append(entry)
        logger.warning(
            "Local fallback dispatch completed (cycle=%s, assignments=%s, reason=%s)",
            entry.cycle,
            len(decisions),
            reason,
        )
        return entry

    def _has_pending_approval(self, action: str, subject_id: str) -> bool:
        """Return whether fallback already queued an approval for a robot or task."""
        return any(
            approval.action == action
            and (
                approval.payload.get("robot_id") == subject_id
                or approval.payload.get("task_id") == subject_id
            )
            for approval in self.pending_approvals.values()
        )

    def _queue_fallback_approval(self, action: str, payload: dict, reasoning: str) -> Decision:
        """Create a human approval for a fallback action without applying it automatically."""
        approval_id = f"fallback-{uuid.uuid4().hex}"
        self.pending_approvals[approval_id] = PendingApproval(
            id=approval_id,
            action=action,
            payload=payload,
            reasoning=reasoning,
            created_at=_now(),
        )
        return Decision(
            action=action,
            robot_id=payload.get("robot_id"),
            task_id=payload.get("task_id"),
            reasoning=f"[pending approval] {reasoning}",
        )

    def _apply_tool_call(self, call: ToolCall) -> tuple[Decision | None, dict]:
        """Validate, apply, and serialize the outcome of one tool call."""
        model_cls = INPUT_MODELS.get(call.name)
        if model_cls is None:
            raise ValueError(f"Unknown tool: {call.name}")

        payload = model_cls.model_validate(call.input)
        reasoning = getattr(payload, "reasoning", None) or getattr(payload, "reason", "")

        if call.name in APPROVAL_REQUIRED_ACTIONS:
            subject_id = getattr(payload, "robot_id", None) or getattr(payload, "task_id", "")
            if self._has_pending_approval(call.name, subject_id):
                return None, {"status": "already_pending_approval"}
            approval = PendingApproval(
                id=call.id,
                action=call.name,
                payload=payload.model_dump(),
                reasoning=reasoning,
                created_at=_now(),
            )
            self.pending_approvals[approval.id] = approval
            return (
                Decision(
                    action=call.name,
                    robot_id=getattr(payload, "robot_id", None),
                    task_id=getattr(payload, "task_id", None),
                    reasoning=f"[pending approval] {reasoning}",
                ),
                {"status": "pending_approval", "approval_id": approval.id},
            )

        handler = getattr(self.tool_handlers, call.name)
        result = handler(payload)
        return (
            Decision(
                action=call.name,
                robot_id=getattr(payload, "robot_id", None),
                task_id=getattr(payload, "task_id", None),
                reasoning=reasoning,
            ),
            result,
        )

    def resolve_approval(
        self,
        approval_id: str,
        action: str,
        modified_payload: dict | None = None,
    ) -> None:
        """Apply, discard, or validate-and-apply a human-reviewed action."""
        approval = self.pending_approvals.get(approval_id)
        if approval is None:
            raise ValueError(f"Unknown pending approval: {approval_id}")
        if action == "reject":
            self.pending_approvals.pop(approval_id)
            approval.status = "rejected"
            return
        if action not in {"approve", "modify"}:
            raise ValueError(f"Unknown approval action: {action}")
        model_cls = INPUT_MODELS[approval.action]
        payload_data = modified_payload if action == "modify" else approval.payload
        if payload_data is None:
            raise ValueError("A modified payload is required for modify")
        payload = model_cls.model_validate(payload_data)
        handler = getattr(self.tool_handlers, approval.action)
        handler(payload)
        self.pending_approvals.pop(approval_id)
        approval.status = "approved"
