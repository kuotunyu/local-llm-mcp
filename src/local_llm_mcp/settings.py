"""Centralized environment-variable configuration.

All tunables live here so tool modules never read `os.environ` directly.
See ../.env.example for the full list with defaults and rationale.
"""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


# --- Ollama connection ------------------------------------------------------
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
# TAIDE (National Science and Technology Council-led Taiwan LLM project) — chosen over
# a generic multilingual model of similar size because it was already pulled locally and
# fits this privacy/zh-TW-focused project.
DEFAULT_MODEL = os.environ.get("LOCAL_LLM_MCP_DEFAULT_MODEL", "cwchang/llama3-taide-lx-8b-chat-alpha1")

# httpx timeouts. Ollama's own Python client defaults `timeout=None` (wait forever) —
# a cold model load + long generation could otherwise block a tool call indefinitely.
OLLAMA_CONNECT_TIMEOUT = _float_env("LOCAL_LLM_MCP_CONNECT_TIMEOUT", 5.0)
OLLAMA_READ_TIMEOUT = _float_env("LOCAL_LLM_MCP_READ_TIMEOUT", 300.0)

# Ollama's own default context length is not trustworthy: its docs disagree with each
# other (2048 / 4096 / VRAM-tiered, depending on which page you read). Always pass
# num_ctx explicitly instead of relying on the server default.
DEFAULT_NUM_CTX = _int_env("LOCAL_LLM_MCP_NUM_CTX", 8192)

# --- Per-tool input length caps (characters) --------------------------------
MAX_PROMPT_CHARS = _int_env("LOCAL_LLM_MCP_MAX_PROMPT_CHARS", 8_000)
MAX_SUMMARIZE_CHARS = _int_env("LOCAL_LLM_MCP_MAX_SUMMARIZE_CHARS", 200_000)

# --- Streamable HTTP transport (Phase 3) ------------------------------------
TRANSPORT = os.environ.get("LOCAL_LLM_MCP_TRANSPORT", "stdio")
HTTP_HOST = os.environ.get("LOCAL_LLM_MCP_HTTP_HOST", "127.0.0.1")
HTTP_PORT = _int_env("LOCAL_LLM_MCP_HTTP_PORT", 8000)
HTTP_PATH = os.environ.get("LOCAL_LLM_MCP_HTTP_PATH", "/mcp")

# Left unset for stdio-only use; server.py refuses to start the HTTP transport
# without it (fail fast rather than silently serving with no auth).
API_KEY = os.environ.get("LOCAL_LLM_MCP_API_KEY")

# Extra Host-header / Origin values to trust in addition to 127.0.0.1/localhost —
# needed when fronting the server with a tunnel (e.g. cloudflared), since FastMCP's
# DNS-rebinding protection (enabled whenever host="127.0.0.1") otherwise rejects any
# Host header that isn't localhost with 421 Invalid Host header. Empty by default:
# the bind address stays 127.0.0.1 regardless: this only widens the *Host header*
# allow-list, it does not open the bind address itself.
EXTRA_ALLOWED_HOSTS = [h for h in os.environ.get("LOCAL_LLM_MCP_EXTRA_ALLOWED_HOSTS", "").split(",") if h]

# --- Optional cloud delegation (web_search tool) -----------------------------
# The one deliberate exception to "nothing leaves the machine": web_search
# sends its query to the Felo cloud API (hybrid privacy routing). Unset ⇒ the
# tool raises a structured error explaining how to enable it; every *_private
# tool stays local-only regardless.
FELO_API_KEY = os.environ.get("FELO_API_KEY")
FELO_API_URL = os.environ.get("LOCAL_LLM_MCP_FELO_API_URL", "https://openapi.felo.ai/v2/chat")
FELO_READ_TIMEOUT = _float_env("LOCAL_LLM_MCP_FELO_READ_TIMEOUT", 120.0)
