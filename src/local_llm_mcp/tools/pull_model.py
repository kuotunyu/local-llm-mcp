"""pull_model — download an Ollama model, reporting progress via MCP progress notifications."""

from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from .. import settings
from ..errors import OllamaUnavailableError
from ..ollama_client import build_client
from ..progress import report_progress

TOOL_NAME = "pull_model"


def register(mcp: FastMCP) -> None:
    @mcp.tool(name=TOOL_NAME)
    async def pull_model(model: str, ctx: Context) -> str:
        """Download an Ollama model, reporting incremental progress as it downloads.

        Not every progress line carries byte counts (e.g. the 'pulling manifest'
        and 'success' lines don't), so progress notifications are only sent for
        lines that have both `total` and `completed`.
        """
        client = build_client()
        last_status = ""
        try:
            async for chunk in await client.pull(model, stream=True):
                last_status = chunk.status
                if chunk.total and chunk.completed is not None:
                    await report_progress(
                        ctx,
                        progress=chunk.completed,
                        total=chunk.total,
                        message=f"{chunk.status}: {chunk.completed}/{chunk.total} bytes",
                    )
                else:
                    await ctx.debug(f"{TOOL_NAME}: {chunk.status}")
        except ConnectionError as exc:
            # `ollama` wraps httpx.ConnectError as the builtin ConnectionError —
            # see ollama_client.py for the same pattern.
            raise OllamaUnavailableError(settings.OLLAMA_HOST) from exc

        return f"Model '{model}' pulled successfully (final status: {last_status})."
