"""Unit tests for tool input validation and request/response wiring.

Each tool's Ollama call is mocked out (patching `chat` in the tool's own
module namespace — `from ..ollama_client import chat` binds a local
reference there, so that's what must be patched) so these tests never
require a running Ollama; only validation logic and the request/response
wiring are exercised. Tools are invoked through a real FastMCP instance's
`call_tool()` (in-process, no transport), so the exact registration/schema
wiring is exercised too — not just the bare Python functions.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from local_llm_mcp import settings
from local_llm_mcp.tools import ask_local, extract_json, summarize_private, translate_private

# `FastMCP.Tool.run()` catches every exception raised inside a tool body —
# including our own ToolError subclasses — and re-raises a fresh generic
# ToolError(f"Error executing tool {name}: {original}"). So the *type* that
# actually propagates out of call_tool() is always plain ToolError; the
# specific subclass's message survives as a substring. This matches what the
# Phase 2/3 e2e tests observed over stdio/HTTP (`"Error executing tool ask_local: ..."`).


def make_fake_response(content: str):
    """A minimal stand-in for ollama.ChatResponse — only `.message.content` is used."""

    class _Message:
        pass

    class _Response:
        pass

    resp = _Response()
    resp.message = _Message()
    resp.message.content = content
    return resp


@pytest.fixture
def mcp(monkeypatch):
    # ctx.debug() (used for tracing inside each tool) needs a bound request
    # context that only exists inside a real client-server session. These are
    # pure unit tests calling FastMCP.call_tool() directly (no transport, no
    # session), so stub it out — we're testing tool logic here, not SDK
    # logging plumbing (that's already exercised by the Phase 2/3 e2e tests).
    monkeypatch.setattr(Context, "debug", AsyncMock())

    server = FastMCP("test-server")
    ask_local.register(server)
    summarize_private.register(server)
    translate_private.register(server)
    extract_json.register(server)
    return server


@pytest.mark.asyncio
async def test_ask_local_rejects_oversized_input(mcp):
    huge = "x" * (settings.MAX_PROMPT_CHARS + 1)
    with pytest.raises(ToolError, match="exceeding the .* limit"):
        await mcp.call_tool("ask_local", {"prompt": huge})


@pytest.mark.asyncio
async def test_ask_local_happy_path(mcp, monkeypatch):
    fake_chat = AsyncMock(return_value=make_fake_response("hello back"))
    monkeypatch.setattr(ask_local, "chat", fake_chat)

    result = await mcp.call_tool("ask_local", {"prompt": "hi", "temperature": 0.5})

    assert fake_chat.await_args.kwargs["model"] == settings.DEFAULT_MODEL
    assert fake_chat.await_args.kwargs["options"]["temperature"] == 0.5
    assert "hello back" in str(result)


@pytest.mark.asyncio
async def test_summarize_private_rejects_oversized_input(mcp):
    huge = "x" * (settings.MAX_SUMMARIZE_CHARS + 1)
    with pytest.raises(ToolError, match="exceeding the .* limit"):
        await mcp.call_tool("summarize_private", {"text": huge})


@pytest.mark.asyncio
async def test_summarize_private_single_chunk_happy_path(mcp, monkeypatch):
    fake_chat = AsyncMock(return_value=make_fake_response("a short summary"))
    monkeypatch.setattr(summarize_private, "chat", fake_chat)

    result = await mcp.call_tool("summarize_private", {"text": "some short text to summarize"})

    fake_chat.assert_awaited_once()
    assert "a short summary" in str(result)


@pytest.mark.asyncio
async def test_translate_private_rejects_oversized_input(mcp):
    huge = "x" * (settings.MAX_PROMPT_CHARS + 1)
    with pytest.raises(ToolError, match="exceeding the .* limit"):
        await mcp.call_tool("translate_private", {"text": huge, "target_lang": "en"})


@pytest.mark.asyncio
async def test_translate_private_happy_path(mcp, monkeypatch):
    fake_chat = AsyncMock(return_value=make_fake_response("Good morning"))
    monkeypatch.setattr(translate_private, "chat", fake_chat)

    result = await mcp.call_tool("translate_private", {"text": "早安", "target_lang": "en"})

    assert "Good morning" in str(result)
    assert fake_chat.await_args.kwargs["model"] == settings.DEFAULT_MODEL


@pytest.mark.asyncio
async def test_extract_json_rejects_oversized_input(mcp):
    huge = "x" * (settings.MAX_PROMPT_CHARS + 1)
    with pytest.raises(ToolError, match="exceeding the .* limit"):
        await mcp.call_tool("extract_json", {"text": huge, "json_schema": {"type": "object"}})


@pytest.mark.asyncio
async def test_extract_json_happy_path(mcp, monkeypatch):
    fake_chat = AsyncMock(return_value=make_fake_response('{"name": "Ming", "age": 28}'))
    monkeypatch.setattr(extract_json, "chat", fake_chat)

    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
    }
    result = await mcp.call_tool("extract_json", {"text": "Ming is 28.", "json_schema": schema})

    assert fake_chat.await_args.kwargs["format"] == schema
    assert fake_chat.await_args.kwargs["options"]["temperature"] == 0
    assert "Ming" in str(result)


@pytest.mark.asyncio
async def test_extract_json_raises_tool_error_on_invalid_json(mcp, monkeypatch):
    fake_chat = AsyncMock(return_value=make_fake_response("not json at all"))
    monkeypatch.setattr(extract_json, "chat", fake_chat)

    with pytest.raises(ToolError):
        await mcp.call_tool("extract_json", {"text": "x", "json_schema": {"type": "object"}})
