"""Thin wrapper around the Google Gemini SDK and its function-calling response."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from agent.tools import TOOL_SCHEMAS

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


@dataclass
class ToolCall:
    """A single function invocation Gemini requested, prior to Pydantic validation."""

    id: str
    name: str
    input: dict[str, Any]


class AgentClient:
    """Calls Gemini with function calling enabled and extracts requested tool calls."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._client: genai.Client | None = None
        self.model = model

    def decide(self, system_prompt: str, snapshot: str, max_tokens: int = 2048) -> list[ToolCall]:
        """Send the snapshot to Gemini and return the function calls it requested."""
        if not self._api_key:
            raise ValueError("GEMINI_API_KEY must be set before running the agent")
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        function_declarations = [
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters_json_schema=tool["input_schema"],
            )
            for tool in TOOL_SCHEMAS
        ]
        response = self._client.models.generate_content(
            model=self.model,
            contents=snapshot,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
                tools=[types.Tool(function_declarations=function_declarations)],
            ),
        )
        return [
            ToolCall(
                id=f"gemini-{uuid.uuid4().hex}",
                name=function_call.name,
                input=dict(function_call.args or {}),
            )
            for function_call in (response.function_calls or [])
        ]
