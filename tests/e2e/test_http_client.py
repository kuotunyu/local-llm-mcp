"""End-to-end tests over the Streamable HTTP transport.

A real ``local-llm-mcp --transport streamable-http`` subprocess is started on
a scratch port and driven with the official MCP Python client SDK. Protocol
initialization, primitive discovery, and Bearer-auth rejection are deliberately
verified without Ollama so these security/protocol contracts run in CI. Tests
that execute model-backed tools remain conditional on a reachable Ollama.
"""

from __future__ import annotations

import os
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


requires_ollama = pytest.mark.skipif(
    not _ollama_reachable(),
    reason=f"Ollama not reachable at {settings.OLLAMA_HOST} — start `ollama serve` to run this model-backed e2e test.",
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
                httpx.get(TEST_URL, timeout=1.0)
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
async def test_http_requires_bearer_token_without_ollama(http_server):
    # The 401 surfaces from a background task inside streamablehttp_client's
    # task group, so it propagates as an ExceptionGroup when the context exits.
    with pytest.raises(BaseExceptionGroup) as exc_info:
        async with streamablehttp_client(TEST_URL, headers={}) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()

    unauthorized = [exc for exc in exc_info.value.exceptions if "401" in str(exc)]
    assert unauthorized, f"expected a 401 somewhere in {exc_info.value.exceptions}"


@pytest.mark.asyncio
async def test_http_protocol_catalog_with_valid_bearer_without_ollama(http_server, api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    async with streamablehttp_client(TEST_URL, headers=headers) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "local-llm-mcp"

            tools = (await session.list_tools()).tools
            assert {tool.name for tool in tools} == {
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
async def test_http_real_tool_call(http_server, api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    async with streamablehttp_client(TEST_URL, headers=headers) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("translate_private", {"text": "午安", "target_lang": "en"})
            assert not result.isError
            assert result.content and result.content[0].text.strip()


@requires_ollama
@pytest.mark.asyncio
async def test_http_pull_model_reports_progress(http_server, api_key):
    """Same regression check as the stdio test, but over Streamable HTTP.

    This only works while the server keeps the SDK default (stateful + SSE):
    under stateless_http/json_response the notification is dropped instead of
    reaching the caller.
    """
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
