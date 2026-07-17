"""Long-text chunking for summarize_private.

Ollama's context window has to hold: the prompt template + the source text +
room for the model's own output. We use a rough character-based heuristic
(not a real tokenizer, which would require pulling in a model-specific
tokenizer dependency) to decide how large a chunk can safely be, then split
on paragraph/sentence boundaries so a chunk is never cut mid-sentence.
"""

from __future__ import annotations

import re

# Rough chars-per-token heuristic. CJK text runs close to 1-1.5 chars/token;
# Latin-script text runs closer to 4 chars/token. We assume the conservative
# (worst-case, CJK-heavy) end so a chunk never overflows the context window.
_CHARS_PER_TOKEN = 1.5

# Fraction of num_ctx reserved for the prompt template + the model's own
# output, leaving the rest of the window for the source text chunk itself.
_RESERVED_FRACTION = 0.35

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[。！？.!?])\s*")


def max_chunk_chars(num_ctx: int) -> int:
    """Safe character budget for one chunk of source text, given a context window."""
    usable_tokens = int(num_ctx * (1 - _RESERVED_FRACTION))
    return max(500, int(usable_tokens * _CHARS_PER_TOKEN))


def split_into_chunks(text: str, max_chars: int) -> list[str]:
    """Split `text` into chunks of at most `max_chars`, preferring paragraph
    then sentence boundaries so a chunk never cuts mid-sentence."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""

    for paragraph in _PARAGRAPH_SPLIT.split(text):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_chars:
            current = paragraph
            continue

        # A single paragraph is itself too long — fall back to sentence splitting.
        for sentence in _SENTENCE_SPLIT.split(paragraph):
            candidate = f"{current} {sentence}" if current else sentence
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # Last resort: a single sentence longer than max_chars gets hard-cut.
                current = sentence[:max_chars]

    if current:
        chunks.append(current)

    return chunks
