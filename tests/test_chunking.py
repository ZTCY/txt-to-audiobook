"""Tests for text chunking boundary conditions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from txt_to_audiobook.parser import split_text_into_chunks


class TestSplitTextIntoChunks:
    """Tests for split_text_into_chunks."""

    def test_short_text_single_chunk(self):
        text = "Hello world."
        chunks = split_text_into_chunks(text, max_length=1000)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].index == 0

    def test_exact_max_length(self):
        text = "A" * 1000
        chunks = split_text_into_chunks(text, max_length=1000)
        assert len(chunks) == 1

    def test_splits_at_chinese_period(self):
        # Create text that exceeds max_length, with a period before the boundary
        text = "A" * 997 + "。BCD"
        chunks = split_text_into_chunks(text, max_length=1000)
        assert len(chunks) == 2
        assert chunks[0].text.endswith("。")
        assert chunks[0].text == "A" * 997 + "。"

    def test_splits_at_newline(self):
        text = "A" * 997 + "\nBCD"
        chunks = split_text_into_chunks(text, max_length=1000)
        assert len(chunks) == 2
        assert chunks[0].text.endswith("\n")

    def test_splits_at_exclamation(self):
        text = "A" * 997 + "!BCD"
        chunks = split_text_into_chunks(text, max_length=1000)
        assert len(chunks) == 2
        assert chunks[0].text.endswith("!")

    def test_splits_at_question(self):
        text = "A" * 997 + "?BCD"
        chunks = split_text_into_chunks(text, max_length=1000)
        assert len(chunks) == 2
        assert chunks[0].text.endswith("?")

    def test_no_punctuation_forces_hard_split(self):
        text = "A" * 2000
        chunks = split_text_into_chunks(text, max_length=1000)
        assert len(chunks) == 2
        assert len(chunks[0].text) == 1000
        assert len(chunks[1].text) == 1000

    def test_chunk_indices_sequential(self):
        text = "A" * 5000
        chunks = split_text_into_chunks(text, max_length=1000)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chapter_index_propagated(self):
        text = "A" * 1500
        chunks = split_text_into_chunks(text, max_length=1000, chapter_index=5)
        for chunk in chunks:
            assert chunk.chapter_index == 5

    def test_empty_text(self):
        chunks = split_text_into_chunks("", max_length=1000)
        assert len(chunks) == 1
        assert chunks[0].text == ""

    def test_ellipsis_as_boundary(self):
        text = "A" * 997 + "…BCD"
        chunks = split_text_into_chunks(text, max_length=1000)
        assert len(chunks) == 2
        assert chunks[0].text.endswith("…")

    def test_chinese_punctuation_priority(self):
        """When multiple punctuation marks exist, should split at the last one."""
        text = "你好。世界！再见。" + "A" * 997
        chunks = split_text_into_chunks(text, max_length=1000)
        assert len(chunks) >= 2

    def test_remaining_text_after_split(self):
        """Text after the split point goes into the next chunk."""
        text = "A" * 992 + "。rest more text here to exceed limit"
        chunks = split_text_into_chunks(text, max_length=1000)
        assert len(chunks) == 2
        assert chunks[1].text == "rest more text here to exceed limit"
