"""Thin wrapper around the official `ollama` Python client.

Centralizes: the httpx timeout (the upstream client defaults to `timeout=None`,
i.e. wait forever), the `num_ctx` default, and
translation of transport-level failures into the structured `ToolError`
subclasses in errors.py so tool code never has to catch raw httpx/ollama
exceptions itself.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import ollama

from . import settings
from .errors import ModelNotFoundError, OllamaTimeoutError, OllamaUnavailableError


def build_client() -> ollama.AsyncClient:
    return ollama.AsyncClient(
        host=settings.OLLAMA_HOST,
        timeout=httpx.Timeout(settings.OLLAMA_READ_TIMEOUT, connect=settings.OLLAMA_CONNECT_TIMEOUT),
    )


async def chat(
    client: ollama.AsyncClient,
    *,
    tool_name: str,
    model: str,
    messages: list[dict[str, str]],
    options: dict[str, Any] | None = None,
    format: str | dict[str, Any] | None = None,
) -> ollama.ChatResponse:
    """Call `client.chat()` with num_ctx defaulted in, translating failures."""
    merged_options = {"num_ctx": settings.DEFAULT_NUM_CTX, **(options or {})}
    try:
        return await client.chat(
            model=model,
            messages=messages,
            options=merged_options,
            format=format,
        )
    except httpx.TimeoutException as exc:
        raise OllamaTimeoutError(tool_name, settings.OLLAMA_READ_TIMEOUT) from exc
    except ConnectionError as exc:
        # The `ollama` client itself catches httpx.ConnectError and re-raises as the
        # builtin ConnectionError (see ollama._client._request_raw) — NOT httpx.ConnectError,
        # so that's what we must catch here. Verified against the installed 0.6.2 source.
        raise OllamaUnavailableError(settings.OLLAMA_HOST) from exc
    except ollama.ResponseError as exc:
        if exc.status_code == 404:
            raise ModelNotFoundError(model) from exc
        raise


def _context_length(model_info: dict[str, Any] | None) -> int | None:
    """Ollama exposes context length under an architecture-prefixed key (e.g.
    'llama.context_length', 'qwen3.context_length') — there is no fixed key
    name, so scan for one ending in '.context_length'.
    """
    if not model_info:
        return None
    for key, value in model_info.items():
        if key.endswith(".context_length"):
            return value
    return None


async def list_local_models_info(client: ollama.AsyncClient) -> list[dict[str, Any]]:
    """Local model catalogue with parameter size, quantization, family, and
    context length. Shared by the list_local_models tool and the
    models://local resource so the two primitives never drift apart."""
    try:
        listing = await client.list()
        shows = await asyncio.gather(*(client.show(entry.model) for entry in listing.models))
    except ConnectionError as exc:
        raise OllamaUnavailableError(settings.OLLAMA_HOST) from exc

    result = []
    for entry, show in zip(listing.models, shows):
        details = entry.details
        result.append(
            {
                "name": entry.model,
                "parameter_size": details.parameter_size if details else None,
                "quantization_level": details.quantization_level if details else None,
                "family": details.family if details else None,
                "context_length": _context_length(show.modelinfo),
                "size_bytes": int(entry.size) if entry.size is not None else None,
            }
        )
    return result
