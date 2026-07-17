"""Tests for the ctx.report_progress() workaround (see RESEARCH.md section 3).

The real bug this guards against: mcp v1.x's own Context.report_progress()
never sets `related_request_id`, so progress notifications get misrouted or
silently dropped under Streamable HTTP. These tests assert our replacement
always forwards `related_request_id=ctx.request_id` and no-ops cleanly when
the client didn't ask for progress (no progressToken).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from local_llm_mcp.progress import report_progress


def make_ctx(progress_token=None, request_id="req-1"):
    session = SimpleNamespace(send_progress_notification=AsyncMock())
    meta = SimpleNamespace(progressToken=progress_token) if progress_token is not None else None
    request_context = SimpleNamespace(meta=meta)
    return SimpleNamespace(session=session, request_context=request_context, request_id=request_id)


@pytest.mark.asyncio
async def test_noop_when_no_progress_token():
    ctx = make_ctx(progress_token=None)
    await report_progress(ctx, progress=1, total=10, message="working")
    ctx.session.send_progress_notification.assert_not_called()


@pytest.mark.asyncio
async def test_noop_when_meta_itself_is_none():
    ctx = make_ctx(progress_token=None)
    ctx.request_context.meta = None
    await report_progress(ctx, progress=1, total=10, message="working")
    ctx.session.send_progress_notification.assert_not_called()


@pytest.mark.asyncio
async def test_forwards_related_request_id_when_token_present():
    ctx = make_ctx(progress_token="token-abc", request_id="req-42")
    await report_progress(ctx, progress=3, total=10, message="step 3/10")

    ctx.session.send_progress_notification.assert_awaited_once_with(
        progress_token="token-abc",
        progress=3,
        total=10,
        message="step 3/10",
        related_request_id="req-42",
    )
