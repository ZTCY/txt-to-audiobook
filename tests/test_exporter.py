"""Tests for exporter: file naming, manifest generation."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from txt_to_audiobook.exporter import (
    generate_manifest,
    merge_audio_files,
    save_manifest,
)
from txt_to_audiobook.models import Chapter, ConversionConfig, ConversionResult


class TestMergeAudioFiles:
    """Tests for merge_audio_files."""

    def test_merges_two_files(self, tmp_path):
        f1 = tmp_path / "a.mp3"
        f2 = tmp_path / "b.mp3"
        f1.write_bytes(b"AAA")
        f2.write_bytes(b"BBB")
        out = tmp_path / "merged.mp3"

        merge_audio_files([f1, f2], out)
        assert out.read_bytes() == b"AAABBB"

    def test_deletes_temp_files(self, tmp_path):
        f1 = tmp_path / "temp1.mp3"
        f2 = tmp_path / "temp2.mp3"
        f1.write_bytes(b"X")
        f2.write_bytes(b"Y")
        out = tmp_path / "out.mp3"

        merge_audio_files([f1, f2], out)
        assert not f1.exists()
        assert not f2.exists()

    def test_handles_missing_temp_file(self, tmp_path):
        f1 = tmp_path / "exists.mp3"
        f1.write_bytes(b"DATA")
        f2 = tmp_path / "missing.mp3"
        out = tmp_path / "out.mp3"

        # Should not raise even if one file is missing
        merge_audio_files([f1, f2], out)
        assert out.read_bytes() == b"DATA"

    def test_empty_list(self, tmp_path):
        out = tmp_path / "out.mp3"
        merge_audio_files([], out)
        assert out.exists()
        assert out.read_bytes() == b""


class TestGenerateManifest:
    """Tests for generate_manifest."""

    def test_manifest_structure(self, tmp_path):
        chapter = Chapter(title="第1章", text="content", index=0)
        config = ConversionConfig(
            voice="zh-CN-YunxiNeural",
            rate="+0%",
            output_dir=tmp_path,
        )
        result = ConversionResult(
            chapter=chapter,
            output_path=tmp_path / "001_第1章.mp3",
            chunks_count=3,
            duration_s=12.5,
            success=True,
        )

        manifest = generate_manifest([result], config, tmp_path / "book.txt")

        assert "source_file" in manifest
        assert "config" in manifest
        assert "summary" in manifest
        assert "chapters" in manifest
        assert manifest["summary"]["total_chapters"] == 1
        assert manifest["summary"]["succeeded"] == 1
        assert manifest["summary"]["failed"] == 0
        assert manifest["chapters"][0]["title"] == "第1章"
        assert manifest["chapters"][0]["success"] is True

    def test_manifest_with_failures(self, tmp_path):
        ch1 = Chapter(title="第1章", text="ok", index=0)
        ch2 = Chapter(title="第2章", text="fail", index=1)
        config = ConversionConfig(voice="test", rate="+0%", output_dir=tmp_path)
        results = [
            ConversionResult(chapter=ch1, output_path=tmp_path / "a.mp3",
                             chunks_count=1, duration_s=5.0, success=True),
            ConversionResult(chapter=ch2, output_path=tmp_path / "b.mp3",
                             chunks_count=0, duration_s=0.0, success=False,
                             error="Network error"),
        ]

        manifest = generate_manifest(results, config, tmp_path / "book.txt")
        assert manifest["summary"]["succeeded"] == 1
        assert manifest["summary"]["failed"] == 1
        assert manifest["chapters"][1]["error"] == "Network error"

    def test_manifest_total_duration(self, tmp_path):
        ch = Chapter(title="Ch", text="x", index=0)
        config = ConversionConfig(voice="v", rate="+0%", output_dir=tmp_path)
        results = [
            ConversionResult(chapter=ch, output_path=tmp_path / "a.mp3",
                             chunks_count=1, duration_s=10.5, success=True),
            ConversionResult(chapter=ch, output_path=tmp_path / "b.mp3",
                             chunks_count=1, duration_s=20.3, success=True),
        ]

        manifest = generate_manifest(results, config, tmp_path / "book.txt")
        assert manifest["summary"]["total_duration_s"] == 30.8


class TestSaveManifest:
    """Tests for save_manifest."""

    def test_writes_json_file(self, tmp_path):
        manifest = {"key": "value", "nested": {"a": 1}}
        path = save_manifest(manifest, tmp_path)
        assert path == tmp_path / "manifest.json"
        assert path.exists()

        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded == manifest

    def test_creates_output_dir_if_missing(self, tmp_path):
        target = tmp_path / "subdir" / "deeper"
        manifest = {"x": 1}
        path = save_manifest(manifest, target)
        assert path.exists()

    def test_unicode_in_manifest(self, tmp_path):
        manifest = {"title": "第1章 测试", "content": "你好世界"}
        path = save_manifest(manifest, tmp_path)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["title"] == "第1章 测试"
