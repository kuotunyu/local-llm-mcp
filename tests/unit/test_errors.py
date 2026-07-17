import pytest
from mcp.server.fastmcp.exceptions import ToolError

from local_llm_mcp.errors import (
    InputTooLongError,
    ModelNotFoundError,
    OllamaTimeoutError,
    OllamaUnavailableError,
)


@pytest.mark.parametrize(
    "exc",
    [
        OllamaUnavailableError("http://127.0.0.1:11434"),
        ModelNotFoundError("qwen3.5:9b"),
        InputTooLongError("ask_local", 9000, 8000),
        OllamaTimeoutError("ask_local", 300.0),
    ],
)
def test_all_errors_are_tool_errors(exc):
    # ToolError is what the SDK converts into a structured isError=True result
    # instead of a raw traceback — see errors.py's module docstring.
    assert isinstance(exc, ToolError)


def test_ollama_unavailable_error_mentions_the_host():
    exc = OllamaUnavailableError("http://127.0.0.1:11434")
    assert "127.0.0.1:11434" in str(exc)


def test_model_not_found_error_mentions_the_model():
    exc = ModelNotFoundError("qwen3.5:9b")
    assert "qwen3.5:9b" in str(exc)


def test_input_too_long_error_mentions_actual_and_limit():
    exc = InputTooLongError("summarize_private", 250_000, 200_000)
    message = str(exc)
    assert "250000" in message
    assert "200000" in message
    assert "summarize_private" in message


def test_timeout_error_mentions_tool_and_duration():
    exc = OllamaTimeoutError("pull_model", 300.0)
    message = str(exc)
    assert "pull_model" in message
    assert "300" in message
