"""Structured tool errors.

Every one of these is a `ToolError`, so the SDK surfaces it to the calling MCP
client as a `CallToolResult(isError=True, ...)` with the message below, instead
of a raw traceback. Only *expected* failure modes (Ollama down, unknown model,
oversized input, timeout) should raise these — let genuinely unexpected
exceptions propagate so the SDK's default handling (and our own logs) catch them.
"""

from __future__ import annotations

from mcp.server.fastmcp.exceptions import ToolError


class OllamaUnavailableError(ToolError):
    def __init__(self, host: str):
        super().__init__(
            f"Cannot reach Ollama at {host}. Check that `ollama serve` is running "
            "and that OLLAMA_HOST is configured correctly."
        )


class ModelNotFoundError(ToolError):
    def __init__(self, model: str):
        super().__init__(
            f"Model '{model}' is not available locally. Call `list_local_models` to see "
            f"what is pulled, or use `pull_model` to download it first."
        )


class InputTooLongError(ToolError):
    def __init__(self, tool: str, actual: int, limit: int):
        super().__init__(
            f"Input to '{tool}' is {actual} characters, exceeding the {limit}-character limit."
        )


class OllamaTimeoutError(ToolError):
    def __init__(self, tool: str, timeout_seconds: float):
        super().__init__(
            f"'{tool}' timed out after {timeout_seconds:.0f}s waiting for Ollama. "
            "The model may be cold-loading, or the input/context length may be too large."
        )
