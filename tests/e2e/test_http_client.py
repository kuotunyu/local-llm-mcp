"""End-to-end test over the Streamable HTTP transport: spins up a real
`local-llm-mcp --transport streamable-http` subprocess on a scratch port,
drives it with the official MCP Python client SDK, and tears it down
afterwards. Requires a reachable Ollama with the configured default model —
skipped automatically otherwise (see test_stdio_client.py for the same guard).
"""

from __future__ import annotations

import secrets
import subprocess
import sys
import time

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from local_llm_mcp import settings

TEST_PORT = 8765
TEST_URL = f"http://127.0.0.1:{TEST_PORT}/mcp"


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


@pytest.fixture(scope="module")
def api_key() -> str:
    return secrets.token_urlsafe(16)


@pytest.fixture(scope="module")
def http_server(api_key):
    env = {
        "LOCAL_LLM_MCP_API_KEY": api_key,
        "LOCAL_LLM_MCP_HTTP_PORT": str(TEST_PORT),
    }
    import os

    proc = subprocess.Popen(
        [sys.executable, "-m", "local_llm_mcp.server", "--transport", "streamable-http"],
        env={**os.environ, **env},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                httpx.get(f"http://127.0.0.1:{TEST_PORT}/mcp", timeout=1.0)
                break
            except httpx.HTTPError:
                time.sleep(0.3)
        else:
            proc.kill()
            raise RuntimeError("local-llm-mcp HTTP server did not come up in time")
        yield proc
    finally:
        proc.kill()
        proc.wait(timeout=5)


@pytest.mark.asyncio
async def test_http_requires_bearer_token(http_server):
    # The 401 surfaces from a background task inside streamablehttp_client's
    # own task group, so it propagates as an (Base)ExceptionGroup when the
    # `async with streamablehttp_client(...)` block itself exits — not
    # necessarily synchronously out of the `session.initialize()` await. Wrap
    # the whole block, matching the behavior confirmed during Phase 3 manual
    # verification (see RESEARCH.md section 2).
    with pytest.raises(BaseExceptionGroup) as exc_info:
        async with streamablehttp_client(TEST_URL, headers={}) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()

    unauthorized = [e for e in exc_info.value.exceptions if "401" in str(e)]
    assert unauthorized, f"expected a 401 somewhere in {exc_info.value.exceptions}"


@pytest.mark.asyncio
async def test_http_initialize_and_real_tool_call(http_server, api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    async with streamablehttp_client(TEST_URL, headers=headers) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "local-llm-mcp"

            result = await session.call_tool("translate_private", {"text": "午安", "target_lang": "en"})
            assert not result.isError
            assert result.content and result.content[0].text.strip()


@pytest.mark.asyncio
async def test_http_pull_model_reports_progress(http_server, api_key):
    """Same regression check as the stdio test, but over Streamable HTTP —
    RESEARCH.md section 3 found this only works if the server keeps the SDK
    default (stateful + SSE) rather than stateless_http/json_response."""
    headers = {"Authorization": f"Bearer {api_key}"}
    progress_events: list[tuple[float, float | None, str | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        progress_events.append((progress, total, message))

    async with streamablehttp_client(TEST_URL, headers=headers) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "pull_model",
                {"model": settings.DEFAULT_MODEL},
                progress_callback=on_progress,
            )
            assert not result.isError
            assert progress_events, "pull_model produced no progress notifications over HTTP"
