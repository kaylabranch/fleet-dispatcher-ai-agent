"""The observe -> decide -> act -> update cycle tying the agent to the simulator."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Protocol

from pydantic import ValidationError

from agent.client import ToolCall
from agent.prompt import build_snapshot, build_system_prompt
from agent.tools import APPROVAL_REQUIRED_ACTIONS, INPUT_MODELS, ToolHandlers
from simulator.events import EventGenerator
from simulator.models import Decision, DecisionLogEntry, PendingApproval
from simulator.world import World


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

    def run_cycle(self, pending_user_message: Optional[str] = None) -> DecisionLogEntry:
        """Execute one observe-decide-act-update cycle and return the resulting log entry."""
        self.event_generator.generate(self.world)

        system_prompt = build_system_prompt()
        snapshot = build_snapshot(self.world, pending_user_message=pending_user_message)

        decisions: list[Decision] = []
        flagged_risks: list[str] = []
        tool_calls = self.agent_client.decide(system_prompt, snapshot)

        for _ in range(8):
            if not tool_calls:
                break
            tool_results: list[dict] = []
            for call in tool_calls:
                try:
                    decision, result = self._apply_tool_call(call)
                    if decision is not None:
                        decisions.append(decision)
                    tool_results.append({"tool_call_id": call.id, "tool_name": call.name, "result": result})
                except (ValidationError, ValueError) as exc:
                    message = f"rejected tool call '{call.name}': {exc}"
                    flagged_risks.append(message)
                    tool_results.append({"tool_call_id": call.id, "tool_name": call.name, "error": str(exc)})
            else:
                snapshot = json.dumps(
                    {
                        "fleet_snapshot": self.world.get_snapshot(),
                        "tool_results": tool_results,
                    },
                    indent=2,
                )
                tool_calls = self.agent_client.decide(system_prompt, snapshot)
                continue
        else:
            flagged_risks.append("agent tool-call limit reached; remaining calls were not applied")

        self.world.tick()

        entry = DecisionLogEntry(
            cycle=self.world.cycle,
            timestamp=_now(),
            decisions=decisions,
            flagged_risks=flagged_risks,
        )
        self.decision_log.append(entry)
        return entry

    def _apply_tool_call(self, call: ToolCall) -> tuple[Decision | None, dict]:
        """Validate, apply, and serialize the outcome of one tool call."""
        model_cls = INPUT_MODELS.get(call.name)
        if model_cls is None:
            raise ValueError(f"Unknown tool: {call.name}")

        payload = model_cls.model_validate(call.input)
        reasoning = getattr(payload, "reasoning", None) or getattr(payload, "reason", "")

        if call.name in APPROVAL_REQUIRED_ACTIONS:
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

    def resolve_approval(self, approval_id: str, approve: bool) -> None:
        """Apply or discard a held action once a human has reviewed it."""
        approval = self.pending_approvals.pop(approval_id, None)
        if approval is None:
            raise ValueError(f"Unknown pending approval: {approval_id}")
        if not approve:
            approval.status = "rejected"
            return
        approval.status = "approved"
        model_cls = INPUT_MODELS[approval.action]
        payload = model_cls.model_validate(approval.payload)
        handler = getattr(self.tool_handlers, approval.action)
        handler(payload)
