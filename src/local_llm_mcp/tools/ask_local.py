"""ask_local — free-form Q&A against a local Ollama model."""

from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from .. import settings
from ..errors import InputTooLongError
from ..ollama_client import build_client, chat

TOOL_NAME = "ask_local"


def register(mcp: FastMCP) -> None:
    @mcp.tool(name=TOOL_NAME)
    async def ask_local(
        prompt: str,
        ctx: Context,
        model: str = settings.DEFAULT_MODEL,
        temperature: float = 0.7,
    ) -> str:
        """Ask a free-form question to a local Ollama model.

        Runs entirely on-device via Ollama — nothing is sent to a cloud LLM.
        Use this for anything sensitive that must never leave the machine.
        """
        if len(prompt) > settings.MAX_PROMPT_CHARS:
            raise InputTooLongError(TOOL_NAME, len(prompt), settings.MAX_PROMPT_CHARS)

        await ctx.debug(f"{TOOL_NAME}: model={model} temperature={temperature} prompt_len={len(prompt)}")

        client = build_client()
        response = await chat(
            client,
            tool_name=TOOL_NAME,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperature},
        )
        return response.message.content
