"""web_search — cloud-delegated live web search via the Felo Chat API.

The deliberate counterpart to every *_private tool in this server: this one
DOES send its input to a cloud service. Together they demonstrate hybrid
privacy routing — sensitive content stays on-device (Ollama), while
public-knowledge questions that need fresh web results are delegated to the
cloud, with the boundary made explicit in each tool's description so the
calling LLM can route correctly. See DESIGN.md for the routing rationale.
"""

from __future__ import annotations

import httpx
from mcp.server.fastmcp import Context, FastMCP

from .. import settings
from ..errors import (
    InputTooLongError,
    WebSearchNotConfiguredError,
    WebSearchUpstreamError,
)

TOOL_NAME = "web_search"


async def _search(query: str) -> dict:
    """POST the query to the Felo Chat API and return the payload dict
    (the `data` object: `answer`, `query_analysis`, `resources`)."""
    headers = {
        "Authorization": f"Bearer {settings.FELO_API_KEY}",
        "Content-Type": "application/json",
        # Cloudflare in front of openapi.felo.ai rejects httpx/urllib default
        # user agents (error 1010) — any explicit product token passes.
        "User-Agent": "local-llm-mcp/0.1",
    }
    timeout = httpx.Timeout(
        connect=settings.OLLAMA_CONNECT_TIMEOUT,
        read=settings.FELO_READ_TIMEOUT,
        write=10.0,
        pool=10.0,
    )
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                settings.FELO_API_URL, json={"query": query}, headers=headers
            )
    except httpx.TimeoutException:
        raise WebSearchUpstreamError(
            f"timed out after {settings.FELO_READ_TIMEOUT:.0f}s waiting for the Felo API"
        )
    except httpx.HTTPError as exc:
        raise WebSearchUpstreamError(f"network error reaching the Felo API: {exc}")

    if response.status_code == 401:
        raise WebSearchUpstreamError("Felo rejected the API key (HTTP 401) — check FELO_API_KEY")
    if response.status_code != 200:
        raise WebSearchUpstreamError(f"Felo API returned HTTP {response.status_code}")

    body = response.json()
    # Wire format wraps the payload: {"status": 200, "code": "OK", "data": {...}}
    return body.get("data") or body


def _format(payload: dict) -> str:
    answer = payload.get("answer") or "(Felo returned no answer)"
    lines = [answer]
    resources = payload.get("resources") or []
    if resources:
        lines.append("")
        lines.append("Sources:")
        for i, res in enumerate(resources[:8], 1):
            title = res.get("title", "(untitled)")
            link = res.get("link") or res.get("url", "")
            lines.append(f"{i}. {title} — {link}")
    return "\n".join(lines)


def register(mcp: FastMCP) -> None:
    @mcp.tool(name=TOOL_NAME)
    async def web_search(query: str, ctx: Context) -> str:
        """Search the live web and get a cited answer via the Felo cloud API.

        PRIVACY BOUNDARY — unlike every *_private tool in this server, the
        query IS sent to a cloud service (Felo). Use it only for
        public-knowledge questions that need fresh web results. Never paste
        private document content into it; route sensitive material to
        ask_local / summarize_private / translate_private / extract_json,
        which run entirely on-device.
        """
        if not settings.FELO_API_KEY:
            raise WebSearchNotConfiguredError()
        if len(query) > settings.MAX_PROMPT_CHARS:
            raise InputTooLongError(TOOL_NAME, len(query), settings.MAX_PROMPT_CHARS)

        await ctx.debug(f"{TOOL_NAME}: query_len={len(query)}")
        return _format(await _search(query))
