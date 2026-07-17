"""models://local — the local Ollama model catalogue as an MCP resource.

This is deliberately a Resource, not a Tool: it's a snapshot of current
machine state a client GETs (and can watch/re-read), not an action with side
effects — see DESIGN.md for the tools-vs-resources rationale. Same underlying
data as the list_local_models tool (tools/list_local_models.py); both share
ollama_client.list_local_models_info().
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .ollama_client import build_client, list_local_models_info


def register(mcp: FastMCP) -> None:
    @mcp.resource("models://local")
    async def local_models() -> str:
        """Snapshot of Ollama models available on this machine, with parameter
        size, quantization level, family, and context length."""
        models = await list_local_models_info(build_client())
        return json.dumps(models, ensure_ascii=False, indent=2)
