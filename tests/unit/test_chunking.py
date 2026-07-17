from local_llm_mcp.chunking import max_chunk_chars, split_into_chunks


def test_max_chunk_chars_scales_with_num_ctx():
    small = max_chunk_chars(2048)
    large = max_chunk_chars(8192)
    assert large > small


def test_max_chunk_chars_has_a_floor():
    # Even a tiny context window should still yield a usable minimum.
    assert max_chunk_chars(1) == 500


def test_short_text_is_a_single_chunk():
    text = "hello world"
    assert split_into_chunks(text, max_chars=1000) == [text]


def test_splits_on_paragraph_boundaries():
    paragraphs = ["A" * 100, "B" * 100, "C" * 100]
    text = "\n\n".join(paragraphs)
    chunks = split_into_chunks(text, max_chars=150)
    assert len(chunks) == 3
    for chunk, expected in zip(chunks, paragraphs):
        assert chunk == expected


def test_packs_multiple_small_paragraphs_into_one_chunk():
    paragraphs = ["A" * 10, "B" * 10, "C" * 10]
    text = "\n\n".join(paragraphs)
    chunks = split_into_chunks(text, max_chars=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_falls_back_to_sentence_splitting_within_an_oversized_paragraph():
    # One "paragraph" (no blank-line breaks) made of several sentences, longer
    # than max_chars as a whole but each sentence individually fits.
    sentences = ["This is sentence one.", "This is sentence two.", "This is sentence three."]
    paragraph = " ".join(sentences)
    chunks = split_into_chunks(paragraph, max_chars=30)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 30
    # No sentence content should be lost.
    rejoined = " ".join(chunks)
    for sentence in sentences:
        assert sentence in rejoined


def test_hard_cuts_a_single_sentence_longer_than_max_chars():
    huge_sentence = "x" * 500 + "."
    chunks = split_into_chunks(huge_sentence, max_chars=100)
    assert all(len(c) <= 100 for c in chunks)
    # Nothing left over beyond what was hard-cut.
    assert sum(len(c) for c in chunks) <= len(huge_sentence)


def test_chinese_sentence_boundaries_are_respected():
    sentences = ["今天天氣很好。", "我們去公園散步。", "然後回家吃晚餐。"]
    paragraph = "".join(sentences)
    chunks = split_into_chunks(paragraph, max_chars=15)
    assert all(len(c) <= 15 for c in chunks)
    rejoined = "".join(chunks)
    for sentence in sentences:
        assert sentence in rejoined


def test_no_chunk_ever_exceeds_max_chars():
    text = ("段落一內容。" * 20 + "\n\n") * 5 + "最後一段沒有句號結尾還很長" * 30
    max_chars = 80
    chunks = split_into_chunks(text, max_chars=max_chars)
    assert all(len(c) <= max_chars for c in chunks)
