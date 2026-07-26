"""Data models for the audiobook pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Chapter:
    """A detected chapter in the source text."""

    title: str
    text: str
    index: int


@dataclass
class Chunk:
    """A text chunk to be synthesized as a single TTS request."""

    text: str
    index: int
    chapter_index: int


@dataclass
class ConversionConfig:
    """Configuration for a conversion run."""

    voice: str = "zh-CN-YunxiNeural"
    rate: str = "+0%"
    output_dir: Path = field(default_factory=Path)
    start_chapter: Optional[int] = None
    end_chapter: Optional[int] = None


@dataclass
class ConversionResult:
    """Result of converting a single chapter."""

    chapter: Chapter
    output_path: Path
    chunks_count: int
    duration_s: float
    success: bool
    error: Optional[str] = None
