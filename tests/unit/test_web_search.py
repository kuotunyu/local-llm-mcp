"""Unit tests for the web_search tool (Felo Chat API delegation).

The HTTP layer is exercised through a fake httpx.AsyncClient patched into the
tool's module namespace, so request wiring (URL, auth header, custom UA,
payload) and response parsing/error mapping are both covered without any
network access. Same FastMCP.call_tool() pattern as test_tools.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from local_llm_mcp import settings
from local_llm_mcp.tools import web_search

FAKE_PAYLOAD = {
    "status": 200,
    "code": "OK",
    "data": {
        "answer": "MCP is an open protocol.",
        "resources": [
            {"title": "Spec", "link": "https://example.com/spec", "snippet": "..."},
            {"title": "No-link entry", "snippet": "..."},
        ],
    },
}


class FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}

    def json(self) -> dict:
        return self._body


class FakeAsyncClient:
    """Stands in for httpx.AsyncClient; records the last request it saw."""

    last_request: dict = {}
    response: FakeResponse = FakeResponse(200, FAKE_PAYLOAD)
    raises: Exception | None = None

    def __init__(self, **kwargs):
        FakeAsyncClient.last_request["client_kwargs"] = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        FakeAsyncClient.last_request.update(url=url, json=json, headers=headers)
        if FakeAsyncClient.raises is not None:
            raise FakeAsyncClient.raises
        return FakeAsyncClient.response


@pytest.fixture
def mcp(monkeypatch):
    monkeypatch.setattr(Context, "debug", AsyncMock())
    monkeypatch.setattr(web_search.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(settings, "FELO_API_KEY", "test-key-123")
    FakeAsyncClient.last_request = {}
    FakeAsyncClient.response = FakeResponse(200, FAKE_PAYLOAD)
    FakeAsyncClient.raises = None

    server = FastMCP("test-server")
    web_search.register(server)
    return server


@pytest.mark.asyncio
async def test_web_search_requires_api_key(mcp, monkeypatch):
    monkeypatch.setattr(settings, "FELO_API_KEY", None)
    with pytest.raises(ToolError, match="FELO_API_KEY"):
        await mcp.call_tool("web_search", {"query": "anything"})


@pytest.mark.asyncio
async def test_web_search_rejects_oversized_query(mcp):
    huge = "x" * (settings.MAX_PROMPT_CHARS + 1)
    with pytest.raises(ToolError, match="exceeding the .* limit"):
        await mcp.call_tool("web_search", {"query": huge})


@pytest.mark.asyncio
async def test_web_search_happy_path_wires_request_and_formats_answer(mcp):
    result = str(await mcp.call_tool("web_search", {"query": "what is MCP?"}))

    sent = FakeAsyncClient.last_request
    assert sent["url"] == settings.FELO_API_URL
    assert sent["json"] == {"query": "what is MCP?"}
    assert sent["headers"]["Authorization"] == "Bearer test-key-123"
    # Cloudflare rejects default python UAs (error 1010) — must send our own.
    assert "local-llm-mcp" in sent["headers"]["User-Agent"]

    assert "MCP is an open protocol." in result
    assert "https://example.com/spec" in result


@pytest.mark.asyncio
async def test_web_search_maps_401_to_tool_error(mcp):
    FakeAsyncClient.response = FakeResponse(401)
    with pytest.raises(ToolError, match="401"):
        await mcp.call_tool("web_search", {"query": "q"})


@pytest.mark.asyncio
async def test_web_search_maps_timeout_to_tool_error(mcp):
    FakeAsyncClient.raises = httpx.ReadTimeout("boom")
    with pytest.raises(ToolError, match="timed out"):
        await mcp.call_tool("web_search", {"query": "q"})


@pytest.mark.asyncio
async def test_web_search_handles_unwrapped_payload(mcp):
    # Defensive: if Felo ever drops the {"data": ...} envelope, parsing still works.
    FakeAsyncClient.response = FakeResponse(200, {"answer": "bare answer", "resources": []})
    result = str(await mcp.call_tool("web_search", {"query": "q"}))
    assert "bare answer" in result
