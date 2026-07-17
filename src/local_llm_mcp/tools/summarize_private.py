"""summarize_private — summarize a block of private text using a local model.

Long inputs are split into chunks (chunking.py) and summarized map-reduce
style: each chunk is summarized independently (progress reported via
progress.py), then the chunk summaries are combined into one final summary.
See PLAN.md section 3.6 / RESEARCH.md section 4.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from .. import settings
from ..chunking import max_chunk_chars, split_into_chunks
from ..errors import InputTooLongError
from ..ollama_client import build_client, chat
from ..progress import report_progress

TOOL_NAME = "summarize_private"

_CHUNK_PROMPT = (
    "Summarize the following excerpt concisely, preserving key facts and figures. "
    "Respond in the same language as the source text.\n\n---\n{text}\n---"
)

_COMBINE_PROMPT = (
    "The following are summaries of consecutive excerpts from one longer document, "
    "in order. Combine them into a single coherent summary, removing redundancy. "
    "Respond in the same language as the excerpt summaries.\n\n---\n{summaries}\n---"
)


def register(mcp: FastMCP) -> None:
    @mcp.tool(name=TOOL_NAME)
    async def summarize_private(
        text: str,
        ctx: Context,
        model: str = settings.DEFAULT_MODEL,
        max_summary_length: int | None = None,
    ) -> str:
        """Summarize private/sensitive text locally.

        Runs entirely on-device via Ollama. Long inputs are automatically split
        into chunks and summarized map-reduce style. `max_summary_length`, if
        given, is a soft character-count hint passed to the model, not a hard
        truncation.
        """
        if len(text) > settings.MAX_SUMMARIZE_CHARS:
            raise InputTooLongError(TOOL_NAME, len(text), settings.MAX_SUMMARIZE_CHARS)

        chunks = split_into_chunks(text, max_chunk_chars(settings.DEFAULT_NUM_CTX))
        await ctx.debug(f"{TOOL_NAME}: model={model} text_len={len(text)} chunks={len(chunks)}")

        client = build_client()
        length_hint = (
            f"\n\nKeep the summary under {max_summary_length} characters." if max_summary_length else ""
        )

        if len(chunks) == 1:
            response = await chat(
                client,
                tool_name=TOOL_NAME,
                model=model,
                messages=[{"role": "user", "content": _CHUNK_PROMPT.format(text=chunks[0]) + length_hint}],
                options={"temperature": 0.3},
            )
            return response.message.content

        # Map: summarize each chunk independently, reporting progress as we go.
        chunk_summaries: list[str] = []
        for i, chunk in enumerate(chunks):
            await report_progress(
                ctx, progress=i, total=len(chunks) + 1,
                message=f"Summarizing chunk {i + 1}/{len(chunks)}",
            )
            response = await chat(
                client,
                tool_name=TOOL_NAME,
                model=model,
                messages=[{"role": "user", "content": _CHUNK_PROMPT.format(text=chunk)}],
                options={"temperature": 0.3},
            )
            chunk_summaries.append(response.message.content)

        # Reduce: combine the per-chunk summaries into one coherent summary.
        await report_progress(
            ctx, progress=len(chunks), total=len(chunks) + 1, message="Combining chunk summaries",
        )
        combined = "\n\n".join(f"[{i + 1}] {s}" for i, s in enumerate(chunk_summaries))
        final_response = await chat(
            client,
            tool_name=TOOL_NAME,
            model=model,
            messages=[{"role": "user", "content": _COMBINE_PROMPT.format(summaries=combined) + length_hint}],
            options={"temperature": 0.3},
        )
        await report_progress(ctx, progress=len(chunks) + 1, total=len(chunks) + 1, message="Done")
        return final_response.message.content
