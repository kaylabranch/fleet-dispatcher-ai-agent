"""Thin wrapper around the Google Gemini SDK and its function-calling response."""

from __future__ import annotations

import os
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from agent.tools import TOOL_SCHEMAS

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_MIN_TIMEOUT_SECONDS = 10.0  # the Gemini API rejects shorter request deadlines
GEMINI_TIMEOUT_SECONDS = max(float(os.environ.get("GEMINI_TIMEOUT_SECONDS", "15")), GEMINI_MIN_TIMEOUT_SECONDS)
GEMINI_MIN_REQUEST_INTERVAL_SECONDS = float(os.environ.get("GEMINI_MIN_REQUEST_INTERVAL_SECONDS", "1"))
logger = logging.getLogger("fleet_dispatch")


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
        self._last_request_started: float | None = None
        self._request_count = 0

    def decide(self, system_prompt: str, snapshot: str, max_tokens: int = 2048) -> list[ToolCall]:
        """Send the snapshot to Gemini and return the function calls it requested."""
        now = time.perf_counter()
        if self._last_request_started is not None:
            wait_seconds = GEMINI_MIN_REQUEST_INTERVAL_SECONDS - (now - self._last_request_started)
            if wait_seconds > 0:
                logger.info("Gemini request spacing wait=%.2fs", wait_seconds)
                time.sleep(wait_seconds)
        started = time.perf_counter()
        self._last_request_started = started
        self._request_count += 1
        logger.info(
            "Gemini request started (number=%s, model=%s, snapshot_chars=%s, system_prompt_chars=%s, max_tokens=%s)",
            self._request_count,
            self.model,
            len(snapshot),
            len(system_prompt),
            max_tokens,
        )
        if not self._api_key:
            logger.error("Gemini request blocked because GEMINI_API_KEY is missing")
            raise ValueError("GEMINI_API_KEY must be set before running the agent")
        if self._client is None:
            self._client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(
                    timeout=int(GEMINI_TIMEOUT_SECONDS * 1000),
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            logger.info(
                "Gemini client initialized (timeout_seconds=%.1f, retries=disabled)",
                GEMINI_TIMEOUT_SECONDS,
            )
        function_declarations = [
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters_json_schema=tool["input_schema"],
            )
            for tool in TOOL_SCHEMAS
        ]
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=snapshot,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens,
                    tools=[types.Tool(function_declarations=function_declarations)],
                ),
            )
        except Exception:
            logger.exception("Gemini request failed (model=%s, duration=%.3fs)", self.model, time.perf_counter() - started)
            raise
        calls = [
            ToolCall(
                id=f"gemini-{uuid.uuid4().hex}",
                name=function_call.name,
                input=dict(function_call.args or {}),
            )
            for function_call in (response.function_calls or [])
        ]
        logger.info(
            "Gemini request completed (model=%s, function_calls=%s, duration=%.3fs)",
            self.model,
            len(calls),
            time.perf_counter() - started,
        )
        return calls
