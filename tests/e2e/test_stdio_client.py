"""End-to-end test over the stdio transport, using the official MCP Python
client SDK to spawn a real `local-llm-mcp` process and drive it exactly as
Claude Desktop/Claude Code would. Requires a reachable Ollama with the
configured default model pulled — skipped automatically otherwise, since this
is a real integration test, not a mocked unit test (see tests/unit for those).
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


pytestmark = pytest.mark.skipif(
    not _ollama_reachable(),
    reason=f"Ollama not reachable at {settings.OLLAMA_HOST} — start `ollama serve` to run this e2e test.",
)


@pytest.mark.asyncio
async def test_stdio_initialize_and_list_tools():
    async with stdio_client(SERVER_CMD) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "local-llm-mcp"

            tools = (await session.list_tools()).tools
            names = {t.name for t in tools}
            assert names == {
                "ask_local",
                "summarize_private",
                "translate_private",
                "extract_json",
                "list_local_models",
                "pull_model",
            }


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
            # or a raw traceback — see errors.py / RESEARCH.md section 4.
            result = await session.call_tool("ask_local", {"prompt": "hi", "model": "no-such-model-xyz"})
            assert result.isError
            assert "not available locally" in result.content[0].text


@pytest.mark.asyncio
async def test_stdio_pull_model_reports_progress():
    """Regression test for the report_progress() workaround (RESEARCH.md
    section 3): pulling an already-present model still streams a real
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
