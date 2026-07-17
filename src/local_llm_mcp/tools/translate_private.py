"""translate_private — translate text between Traditional Chinese and English, locally."""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import Context, FastMCP

from .. import settings
from ..errors import InputTooLongError
from ..ollama_client import build_client, chat

TOOL_NAME = "translate_private"

_PROMPT_TEMPLATE = (
    "Translate the following text into {target_language}. Output only the "
    "translation, with no explanation or commentary.\n\n---\n{text}\n---"
)

_LANGUAGE_NAMES = {
    "zh-TW": "Traditional Chinese (Taiwan)",
    "en": "English",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool(name=TOOL_NAME)
    async def translate_private(
        text: str,
        target_lang: Literal["zh-TW", "en"],
        ctx: Context,
        model: str = settings.DEFAULT_MODEL,
    ) -> str:
        """Translate private/sensitive text between Traditional Chinese and English, locally.

        `target_lang` is the language to translate INTO — the source language is
        inferred from the input text, so translating either direction just means
        picking the opposite `target_lang`.
        """
        if len(text) > settings.MAX_PROMPT_CHARS:
            raise InputTooLongError(TOOL_NAME, len(text), settings.MAX_PROMPT_CHARS)

        await ctx.debug(f"{TOOL_NAME}: model={model} target_lang={target_lang} text_len={len(text)}")

        client = build_client()
        prompt = _PROMPT_TEMPLATE.format(target_language=_LANGUAGE_NAMES[target_lang], text=text)
        response = await chat(
            client,
            tool_name=TOOL_NAME,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2},
        )
        return response.message.content
