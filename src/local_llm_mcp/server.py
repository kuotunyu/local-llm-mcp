"""FastMCP server construction and CLI entrypoint for local-llm-mcp.

Two transports, selected by --transport or LOCAL_LLM_MCP_TRANSPORT (CLI flag
wins): `stdio` (default, no auth — process-level trust, used by Claude
Desktop/Code) and `streamable-http` (API-key auth via auth.py, used by
clients that connect directly rather than through a cloud-brokered
connector — see RESEARCH.md sections 5/6/7/8 for why Claude Desktop can't
use the HTTP transport at all).

IMPORTANT: never print to stdout. The stdio transport uses stdout for JSON-RPC
framing — any stray print() corrupts the protocol stream. All logging below
goes to stderr (see RESEARCH.md section 1 / official MCP debugging docs).
"""

from __future__ import annotations

import argparse
import logging
import sys

from mcp.server.fastmcp import FastMCP

from . import prompts, resources, settings
from .auth import StaticKeyVerifier, build_auth_settings
from .tools import (
    ask_local,
    extract_json,
    list_local_models,
    pull_model,
    summarize_private,
    translate_private,
)

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _register_all(mcp: FastMCP) -> None:
    ask_local.register(mcp)
    summarize_private.register(mcp)
    translate_private.register(mcp)
    extract_json.register(mcp)
    list_local_models.register(mcp)
    pull_model.register(mcp)
    resources.register(mcp)
    prompts.register(mcp)


# Module-level stdio server: no env requirements to construct, so plain
# `import local_llm_mcp.server` (as used by tests and `mcp dev`) keeps working
# without needing LOCAL_LLM_MCP_API_KEY set.
mcp = FastMCP("local-llm-mcp")
_register_all(mcp)


def build_http_server() -> FastMCP:
    """Build a separate FastMCP instance configured for the Streamable HTTP
    transport. Kept separate from the module-level `mcp` (stdio) instance
    because it has a hard requirement (API key) that stdio must not inherit.
    """
    if not settings.API_KEY:
        raise SystemExit(
            "LOCAL_LLM_MCP_API_KEY must be set to run the Streamable HTTP transport.\n"
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    resource_server_url = f"http://{settings.HTTP_HOST}:{settings.HTTP_PORT}{settings.HTTP_PATH}"
    http_mcp = FastMCP(
        "local-llm-mcp",
        host=settings.HTTP_HOST,
        port=settings.HTTP_PORT,
        streamable_http_path=settings.HTTP_PATH,
        token_verifier=StaticKeyVerifier(settings.API_KEY),
        auth=build_auth_settings(resource_server_url),
        # Deliberately NOT setting stateless_http/json_response: the SDK default
        # (stateful + SSE) is the only mode where pull_model's progress
        # notifications have any chance of being delivered — see RESEARCH.md
        # section 3.
    )
    _register_all(http_mcp)
    return http_mcp


def main() -> None:
    parser = argparse.ArgumentParser(prog="local-llm-mcp")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=settings.TRANSPORT,
        help="Transport to run (default: stdio, or LOCAL_LLM_MCP_TRANSPORT env var)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        logger.info(
            "Starting local-llm-mcp (stdio transport, default_model=%s, ollama_host=%s)",
            settings.DEFAULT_MODEL,
            settings.OLLAMA_HOST,
        )
        mcp.run()
    else:
        logger.info(
            "Starting local-llm-mcp (streamable-http on %s:%s%s, default_model=%s, ollama_host=%s)",
            settings.HTTP_HOST,
            settings.HTTP_PORT,
            settings.HTTP_PATH,
            settings.DEFAULT_MODEL,
            settings.OLLAMA_HOST,
        )
        build_http_server().run(transport="streamable-http")


if __name__ == "__main__":
    main()
