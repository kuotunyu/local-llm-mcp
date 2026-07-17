"""Workaround for a known mcp v1.x bug: `Context.report_progress()` never sets
`related_request_id` on the outgoing notification, so under Streamable HTTP the
progress message gets routed to the wrong (standalone GET) stream, or silently
dropped entirely in stateless/JSON-response mode. See RESEARCH.md section 3
(issues #953 / #2001 — fixed only in the v2 `mcp.server.mcpserver` module, never
backported to v1's `mcp.server.fastmcp`).

stdio has no such multiplexed-stream routing problem, but every tool in this
project calls this helper instead of `ctx.report_progress()` directly, so the
workaround lives in exactly one place and is trivial to drop once the SDK fixes
it upstream (verify with the repro command in RESEARCH.md section 3 before
removing this).
"""

from __future__ import annotations

from mcp.server.fastmcp import Context


async def report_progress(
    ctx: Context,
    progress: float,
    total: float | None = None,
    message: str | None = None,
) -> None:
    meta = ctx.request_context.meta
    progress_token = meta.progressToken if meta else None
    if progress_token is None:
        # Client didn't ask for progress on this call — nothing to do.
        return
    await ctx.session.send_progress_notification(
        progress_token=progress_token,
        progress=progress,
        total=total,
        message=message,
        related_request_id=ctx.request_id,
    )
