"""Tests for chapter detection and parser utilities."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from txt_to_audiobook.parser import (
    clean_text,
    sanitize_filename,
    split_chapters,
    split_text_into_chunks,
)
from txt_to_audiobook.models import Chapter


class TestCleanText:
    """Tests for clean_text."""

    def test_removes_bom(self):
        text = "\ufeffHello world"
        assert clean_text(text) == "Hello world"

    def test_normalizes_crlf(self):
        text = "Line1\r\nLine2\rLine3\n"
        assert clean_text(text) == "Line1\nLine2\nLine3"

    def test_collapses_excessive_blank_lines(self):
        text = "Para1\n\n\n\n\nPara2"
        assert clean_text(text) == "Para1\n\nPara2"

    def test_strips_whitespace(self):
        text = "  \n  Hello  \n  "
        assert clean_text(text) == "Hello"


class TestSplitChapters:
    """Tests for split_chapters."""

    def test_detects_第X章(self):
        text = "第1章 开始\n内容一\n第2章 结束\n内容二"
        chapters = split_chapters(text)
        assert len(chapters) == 2
        assert chapters[0].title == "第1章"
        assert chapters[1].title == "第2章"
        assert "开始" in chapters[0].text
        assert "结束" in chapters[1].text

    def test_detects_第X回(self):
        text = "第一回 桃园结义\n内容A\n第二回 虎牢关\n内容B"
        chapters = split_chapters(text)
        assert len(chapters) == 2
        assert chapters[0].title == "第一回"
        assert chapters[1].title == "第二回"

    def test_detects_chapter_english(self):
        text = "Chapter 1 Beginning\nContent A\nChapter 2 End\nContent B"
        chapters = split_chapters(text)
        assert len(chapters) == 2
        assert chapters[0].title == "Chapter 1"
        assert chapters[1].title == "Chapter 2"

    def test_detects_第X节(self):
        text = "第1节 引言\n内容A\n第2节 正文\n内容B"
        chapters = split_chapters(text)
        assert len(chapters) == 2
        assert chapters[0].title == "第1节"
        assert chapters[1].title == "第2节"

    def test_no_chapters_returns_single(self):
        text = "This is a plain text without any chapter markers."
        chapters = split_chapters(text)
        assert len(chapters) == 1
        assert chapters[0].title == "Full Text"
        assert chapters[0].text == text

    def test_mixed_formats(self):
        text = "第1章 开始\n内容一\nChapter 2 Middle\n内容二\n第3回 结束\n内容三"
        chapters = split_chapters(text)
        assert len(chapters) == 3
        assert chapters[0].title == "第1章"
        assert chapters[1].title == "Chapter 2"
        assert chapters[2].title == "第3回"

    def test_chapter_indices_are_sequential(self):
        text = "第1章 A\nx\n第2章 B\ny\n第3章 C\nz"
        chapters = split_chapters(text)
        for i, ch in enumerate(chapters):
            assert ch.index == i

    def test_chinese_number_chapters(self):
        text = "第一章 开始\nx\n第二章 继续\ny\n第十章 结束\nz"
        chapters = split_chapters(text)
        assert len(chapters) == 3
        assert chapters[0].title == "第一章"
        assert chapters[1].title == "第二章"
        assert chapters[2].title == "第十章"


class TestSanitizeFilename:
    """Tests for sanitize_filename."""

    def test_removes_illegal_chars(self):
        title = 'file:*?"<>|name'
        result = sanitize_filename(title)
        assert all(c not in result for c in '\\/:*?"<>|')

    def test_truncates_long_title(self):
        title = "A" * 100
        result = sanitize_filename(title, max_length=50)
        assert len(result) == 50

    def test_preserves_normal_text(self):
        title = "第一章 开端"
        result = sanitize_filename(title)
        assert result == title

    def test_empty_string(self):
        assert sanitize_filename("") == ""

    def test_custom_max_length(self):
        title = "ABCDEFGH"
        result = sanitize_filename(title, max_length=4)
        assert result == "ABCD"
