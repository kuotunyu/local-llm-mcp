"""list_local_models — list locally available Ollama models with metadata.

Same underlying data as the models://local resource (resources.py) — this is
the action-oriented "call it and get the current list back" primitive, while
the resource is the state-snapshot primitive. Both share
ollama_client.list_local_models_info() so they can't drift apart.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from ..ollama_client import build_client, list_local_models_info

TOOL_NAME = "list_local_models"


def register(mcp: FastMCP) -> None:
    @mcp.tool(name=TOOL_NAME)
    async def list_local_models(ctx: Context) -> list[dict[str, Any]]:
        """List Ollama models available on this machine, with parameter size,
        quantization level, family, and context length."""
        return await list_local_models_info(build_client())
