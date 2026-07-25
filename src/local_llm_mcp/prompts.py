"""Reusable MCP prompt templates.

These wrap raw user text into a task-specific instruction — the kind of
boilerplate a user would otherwise retype every time.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.prompt(title="Summarize for a formal report")
    def summarize_for_report(text: str) -> str:
        """Wrap text in an instruction to summarize it in a register suitable
        for inclusion in a formal report, then hand it to summarize_private."""
        return (
            "Summarize the following text in a concise, formal register suitable "
            "for inclusion in a business or government report — neutral tone, "
            "no colloquialisms, lead with the key conclusion.\n\n---\n"
            f"{text}\n---"
        )

    @mcp.prompt(title="Formal Chinese-English translation")
    def translate_formal(text: str, target_lang: str) -> str:
        """Wrap text in an instruction to translate it in a formal written
        register, then hand it to translate_private."""
        return (
            f"Translate the following text into {target_lang}, using formal "
            "written register (書面語) rather than colloquial speech. Output "
            f"only the translation.\n\n---\n{text}\n---"
        )
