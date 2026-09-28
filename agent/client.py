"""Thin wrapper around the Anthropic SDK, isolated so tool handlers can be tested without it."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic

from agent.tools import TOOL_SCHEMAS

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")


@dataclass
class ToolCall:
    """A single tool invocation Claude requested, prior to Pydantic validation."""

    id: str
    name: str
    input: dict[str, Any]


class AgentClient:
    """Calls Claude with tool use enabled and extracts the resulting tool calls."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        self._client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model

    def decide(self, system_prompt: str, snapshot: str, max_tokens: int = 2048) -> list[ToolCall]:
        """Send the snapshot to Claude and return the tool calls it requested."""
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=TOOL_SCHEMAS,
            messages=[{"role": "user", "content": snapshot}],
        )
        return [
            ToolCall(id=block.id, name=block.name, input=block.input)
            for block in response.content
            if block.type == "tool_use"
        ]
