"""End-to-end tests over the stdio transport using the official MCP Python
client SDK to spawn a real ``local-llm-mcp`` process.

Protocol discovery is intentionally exercised without Ollama so CI proves the
server can initialize and advertise its MCP surface on every run. Tests that
actually execute model-backed tools remain conditional on a reachable Ollama.
"""

from __future__ import annotations

import sys

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from local_llm_mcp import settings

SERVER_CMD = StdioServerParameters(command=sys.executable, args=["-m", "local_llm_mcp.server"])


def _ollama_reachable() -> bool:
    try:
        httpx.get(settings.OLLAMA_HOST, timeout=2.0)
        return True
    except httpx.HTTPError:
        return False


requires_ollama = pytest.mark.skipif(
    not _ollama_reachable(),
    reason=f"Ollama not reachable at {settings.OLLAMA_HOST} — start `ollama serve` to run this model-backed e2e test.",
)


@pytest.mark.asyncio
async def test_stdio_protocol_catalog_without_ollama():
    """Initialization and primitive discovery must not require model inference."""
    async with stdio_client(SERVER_CMD) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "local-llm-mcp"

            tools = (await session.list_tools()).tools
            tool_names = {tool.name for tool in tools}
            assert tool_names == {
                "ask_local",
                "summarize_private",
                "translate_private",
                "extract_json",
                "list_local_models",
                "pull_model",
                "web_search",
            }

            resources = (await session.list_resources()).resources
            assert {str(resource.uri) for resource in resources} == {"models://local"}

            prompts = (await session.list_prompts()).prompts
            assert {prompt.name for prompt in prompts} == {
                "summarize_for_report",
                "translate_formal",
            }


@requires_ollama
@pytest.mark.asyncio
async def test_stdio_real_tool_call_and_error_path():
    async with stdio_client(SERVER_CMD) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Happy path: a real round-trip through Ollama.
            result = await session.call_tool("translate_private", {"text": "早安", "target_lang": "en"})
            assert not result.isError
            assert result.content and result.content[0].text.strip()

            # Structured error path: calling a model that isn't pulled locally
            # must come back as isError=True with our own message, not a crash
            # or a raw traceback — see errors.py.
            result = await session.call_tool("ask_local", {"prompt": "hi", "model": "no-such-model-xyz"})
            assert result.isError
            assert "not available locally" in result.content[0].text


@requires_ollama
@pytest.mark.asyncio
async def test_stdio_pull_model_reports_progress():
    """Regression test for the report_progress() workaround in progress.py:
    pulling an already-present model still streams a real
    progress sequence from Ollama, so this asserts we actually receive
    at least one well-formed notification, not just that the call succeeds.
    """
    progress_events: list[tuple[float, float | None, str | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        progress_events.append((progress, total, message))

    async with stdio_client(SERVER_CMD) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "pull_model",
                {"model": settings.DEFAULT_MODEL},
                progress_callback=on_progress,
            )
            assert not result.isError
            assert progress_events, "pull_model produced no progress notifications"
            for progress, total, _message in progress_events:
                if total is not None:
                    assert 0 <= progress <= total
