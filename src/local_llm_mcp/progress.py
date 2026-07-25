"""Workaround for an mcp v1.x routing bug: `Context.report_progress()` does not
set `related_request_id` on the outgoing notification, so under Streamable HTTP
the progress message gets routed to the wrong (standalone GET) stream, or
silently dropped entirely in stateless/JSON-response mode. `Context.log()` in
the same SDK file does pass the field — that contrast is what identifies this as
an omission rather than a deliberate design. Tracked upstream as issues #953 and
#2001 in modelcontextprotocol/python-sdk.

Upstream status, rechecked 2026-07-25: fixed on a maintenance branch, but not in
anything installable. The v2 line got the missing field in `mcp.server.mcpserver`
(#2002 proposed the line, #2038 landed it). On the v1 line, PR #2994 added it to
`mcp/server/fastmcp/server.py` on the `v1.x` branch on 2026-06-26 — roughly 46
minutes after 1.28.1 was uploaded to PyPI, so it missed that release, and 1.28.1
is still the newest 1.x. Checked the `v1.28.0` and `v1.28.1` tags directly:
neither carries the field. Every version inside this project's
`mcp>=1.28.1,<2.0` pin therefore still needs this helper.

stdio has no such multiplexed-stream routing problem, but every tool in this
project calls this helper instead of `ctx.report_progress()` directly, so the
workaround lives in exactly one place. Drop it once a 1.x release containing
#2994 ships — confirm against the installed version first with:

    python -c "import inspect, mcp.server.fastmcp.server as s; print(inspect.getsource(s.Context.report_progress))"
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
