"""Latency benchmark for local-llm-mcp tools, across two model sizes.

Manual script, not part of the pytest suite — it hits a real Ollama and takes
a few minutes. Run with: `uv run python scripts/bench_latency.py`

Each model gets one untimed warmup call first, so the reported numbers
reflect steady-state inference speed rather than one-time disk-to-VRAM model
load time (which is dominated by file size / disk speed, not the thing this
benchmark is trying to compare).
"""

from __future__ import annotations

import asyncio
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_CMD = StdioServerParameters(command=sys.executable, args=["-m", "local_llm_mcp.server"])

DEFAULT_MODEL = "cwchang/llama3-taide-lx-8b-chat-alpha1"  # 8.0B, Q5_K_M
SMALL_MODEL = "qwen2.5:3b"  # 3B, deliberately a different model family

SHORT_TEXT = "今天天氣很好,適合出門散步。"
LONG_TEXT = (
    "台灣證券交易所今日公布,受惠於半導體與AI相關產業的強勁需求,"
    "加權股價指數收盤上漲逾百點,成交量創下近三個月新高。分析師指出,"
    "外資近期持續回補台股,主要聚焦於晶圓代工與記憶體相關類股,"
    "預期在未來幾季企業獲利動能將持續增溫。"
) * 12

SIMPLE_SCHEMA = {
    "type": "object",
    "properties": {"sentiment": {"type": "string"}},
    "required": ["sentiment"],
}
COMPLEX_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "occupation": {"type": "string"},
        "location": {"type": "string"},
        "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
    },
    "required": ["name", "age", "occupation", "location", "sentiment"],
}
EXTRACT_TEXT = "王小明,28歲,住台北,是一名軟體工程師,今天心情很好。"


async def timed_call(session: ClientSession, name: str, arguments: dict) -> tuple[float, bool, str]:
    start = time.perf_counter()
    result = await session.call_tool(name, arguments)
    elapsed = time.perf_counter() - start
    text = result.content[0].text if result.content else ""
    return elapsed, result.isError, text


async def run_for_model(session: ClientSession, model: str) -> list[tuple[str, str, float]]:
    print(f"  warming up {model}...", file=sys.stderr)
    await timed_call(session, "ask_local", {"prompt": "hi", "model": model})

    rows = []

    elapsed, is_error, _ = await timed_call(session, "ask_local", {"prompt": SHORT_TEXT, "model": model})
    rows.append(("ask_local", f"短(~{len(SHORT_TEXT)}字)", elapsed, is_error))

    elapsed, is_error, _ = await timed_call(
        session, "ask_local", {"prompt": LONG_TEXT[:500], "model": model}
    )
    rows.append(("ask_local", "長(~500字)", elapsed, is_error))

    elapsed, is_error, _ = await timed_call(
        session, "summarize_private", {"text": SHORT_TEXT, "model": model}
    )
    rows.append(("summarize_private", "短文(單一 chunk)", elapsed, is_error))

    elapsed, is_error, _ = await timed_call(
        session, "summarize_private", {"text": LONG_TEXT, "model": model}
    )
    rows.append(("summarize_private", f"長文({len(LONG_TEXT)}字)", elapsed, is_error))

    elapsed, is_error, _ = await timed_call(
        session, "translate_private", {"text": SHORT_TEXT, "target_lang": "en", "model": model}
    )
    rows.append(("translate_private", "一段落", elapsed, is_error))

    elapsed, is_error, _ = await timed_call(
        session,
        "extract_json",
        {"text": EXTRACT_TEXT, "json_schema": SIMPLE_SCHEMA, "model": model},
    )
    rows.append(("extract_json", "簡單 schema", elapsed, is_error))

    elapsed, is_error, _ = await timed_call(
        session,
        "extract_json",
        {"text": EXTRACT_TEXT, "json_schema": COMPLEX_SCHEMA, "model": model},
    )
    rows.append(("extract_json", "複雜 schema", elapsed, is_error))

    return rows


async def main() -> None:
    async with stdio_client(SERVER_CMD) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            list_elapsed, _, _ = await timed_call(session, "list_local_models", {})

            print(f"benchmarking {DEFAULT_MODEL}...", file=sys.stderr)
            default_rows = await run_for_model(session, DEFAULT_MODEL)
            print(f"benchmarking {SMALL_MODEL}...", file=sys.stderr)
            small_rows = await run_for_model(session, SMALL_MODEL)

    def fmt(elapsed: float, is_error: bool) -> str:
        return f"{elapsed:.2f}s" + (" (error)" if is_error else "")

    print()
    print(f"| 工具 | 輸入大小 | {DEFAULT_MODEL}(8B)延遲 | {SMALL_MODEL}(3B)延遲 | 備註 |")
    print("|---|---|---|---|---|")
    print(f"| list_local_models | — | {list_elapsed:.2f}s | (不逐模型測,見備註) | 不涉及模型推論,單次量測即可 |")
    for (tool, size, t1, e1), (_, _, t2, e2) in zip(default_rows, small_rows):
        print(f"| {tool} | {size} | {fmt(t1, e1)} | {fmt(t2, e2)} | |")


if __name__ == "__main__":
    asyncio.run(main())
