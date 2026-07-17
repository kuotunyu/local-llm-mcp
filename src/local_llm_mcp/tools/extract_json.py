"""extract_json — extract structured data from text using a caller-supplied JSON Schema.

The schema is provided by the CALLER at call time, not a fixed Pydantic model —
so this tool cannot rely on the SDK's static `outputSchema` auto-generation
(that's derived from the Python return type annotation, not from runtime
input). Instead it passes the caller's schema straight to Ollama's `format=`
structured-output parameter and hands back the parsed JSON directly, with
`structured_output=False` on the decorator so the SDK doesn't also try to
generate a generic schema from the `dict` return annotation. See PLAN.md
section 3.7.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from .. import settings
from ..errors import InputTooLongError
from ..ollama_client import build_client, chat

TOOL_NAME = "extract_json"

_PROMPT_TEMPLATE = (
    "Extract structured data from the following text according to the required "
    "JSON schema. Respond with ONLY a single JSON object matching the schema — "
    "no explanation, no markdown formatting.\n\n"
    "Schema:\n{schema}\n\n---\n{text}\n---"
)


def register(mcp: FastMCP) -> None:
    @mcp.tool(name=TOOL_NAME, structured_output=False)
    async def extract_json(
        text: str,
        json_schema: dict[str, Any],
        ctx: Context,
        model: str = settings.DEFAULT_MODEL,
    ) -> dict[str, Any]:
        """Extract structured data from private/sensitive text locally, per a
        caller-supplied JSON Schema, using Ollama's constrained decoding.

        Runs entirely on-device — the schema and text never leave the machine.
        Temperature is fixed at 0 for determinism, per Ollama's own
        structured-output guidance (also restated in the prompt).
        """
        if len(text) > settings.MAX_PROMPT_CHARS:
            raise InputTooLongError(TOOL_NAME, len(text), settings.MAX_PROMPT_CHARS)

        await ctx.debug(f"{TOOL_NAME}: model={model} text_len={len(text)}")

        client = build_client()
        prompt = _PROMPT_TEMPLATE.format(schema=json.dumps(json_schema), text=text)
        response = await chat(
            client,
            tool_name=TOOL_NAME,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},
            format=json_schema,
        )
        try:
            return json.loads(response.message.content)
        except json.JSONDecodeError as exc:
            raise ToolError(f"Model returned invalid JSON for the given schema: {exc}") from exc
