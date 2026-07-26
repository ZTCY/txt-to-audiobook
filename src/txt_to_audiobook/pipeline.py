"""Core pipeline: orchestrates parsing, TTS synthesis, and export."""

import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

from .config import TEMP_DIR
from .exporter import enhance_audio, generate_manifest, merge_audio_files, save_manifest
from .models import Chapter, Chunk, ConversionConfig, ConversionResult
from .parser import clean_text, sanitize_filename, split_chapters, split_text_into_chunks
from .tts.base import TTSProvider

logger = logging.getLogger(__name__)


class AudiobookPipeline:
    """Orchestrates the full TXT-to-MP3 conversion process.

    Supports pause/resume/stop/skip via thread-safe event flags,
    chunk-level caching (resumes from where it left off), and
    manifest.json generation.
    """

    def __init__(self, config: ConversionConfig, tts_provider: TTSProvider):
        """Initialize the pipeline.

        Args:
            config: Conversion configuration (voice, rate, ranges, etc.).
            tts_provider: The TTS provider to use for synthesis.
        """
        self.config = config
        self.tts = tts_provider

        # Thread-safe control flags
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._skip_event = threading.Event()

        # Callbacks for progress reporting (set by CLI/GUI)
        self.on_chunk_start: Optional[Callable[[int, int, str], None]] = None
        self.on_chunk_done: Optional[Callable[[int, int], None]] = None
        self.on_chapter_start: Optional[Callable[[int, int, str], None]] = None
        self.on_chapter_done: Optional[Callable[[ConversionResult], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None

    # ---- Public control API ----

    def pause(self) -> None:
        """Pause the pipeline."""
        self._pause_event.set()

    def resume(self) -> None:
        """Resume the pipeline."""
        self._pause_event.clear()

    def stop(self) -> None:
        """Request the pipeline to stop."""
        self._stop_event.set()
        self._pause_event.clear()

    def skip_current(self) -> None:
        """Request to skip the current chapter."""
        self._skip_event.set()

    @property
    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    # ---- Internal helpers ----

    def _log(self, message: str) -> None:
        if self.on_log:
            self.on_log(message)
        else:
            logger.info(message)

    def _wait_if_paused(self) -> bool:
        """Block while paused. Returns False if stop was requested."""
        while self._pause_event.is_set() and not self._stop_event.is_set():
            time.sleep(0.3)
        return not self._stop_event.is_set()

    def _should_break(self) -> bool:
        """Check if the current chapter should be interrupted (stop or skip)."""
        return self._stop_event.is_set() or self._skip_event.is_set()

    # ---- Main conversion entry point ----

    async def convert(self, txt_path: Path) -> List[ConversionResult]:
        """Convert a TXT file to audiobook MP3 files.

        Args:
            txt_path: Path to the source TXT file.

        Returns:
            A list of ConversionResult objects, one per chapter.
        """
        # Reset flags
        self._stop_event.clear()
        self._pause_event.clear()
        self._skip_event.clear()

        # Read and clean text
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
        except UnicodeDecodeError:
            with open(txt_path, "r", encoding="gbk") as f:
                raw_text = f.read()

        text = clean_text(raw_text)
        self._log(f"File size: {len(text)} characters")

        # Split into chapters
        chapters = split_chapters(text)
        self._log(f"Detected {len(chapters)} chapters")

        # Apply chapter range filter
        start = self.config.start_chapter
        end = self.config.end_chapter
        if start is not None or end is not None:
            start_idx = (start or 1) - 1
            end_idx = end or len(chapters)
            start_idx = max(0, start_idx)
            end_idx = min(len(chapters), end_idx)
            chapters = chapters[start_idx:end_idx]
            self._log(f"Will process chapters {start_idx + 1} to {end_idx} ({len(chapters)} chapters)")

        if not chapters:
            self._log("No chapters to process")
            return []

        # Prepare output directory
        book_name = txt_path.stem
        output_dir = Path(self.config.output_dir or "output") / book_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare temp directory
        temp_dir = Path(TEMP_DIR)
        temp_dir.mkdir(parents=True, exist_ok=True)

        actual_start = start if start is not None else 1
        results: List[ConversionResult] = []

        for i, chapter in enumerate(chapters):
            if not self._wait_if_paused():
                break
            if self._stop_event.is_set():
                break

            self._skip_event.clear()
            real_chapter_num = actual_start + i

            if self.on_chapter_start:
                self.on_chapter_start(i + 1, len(chapters), chapter.title)
            self._log(f"Converting: {chapter.title} ({i + 1}/{len(chapters)})")

            result = await self._convert_chapter(
                chapter=chapter,
                real_chapter_num=real_chapter_num,
                output_dir=output_dir,
                temp_dir=temp_dir,
            )
            results.append(result)

            if result.success:
                self._log(f"Done: {chapter.title}")
            else:
                self._log(f"Skipped/Failed: {chapter.title}")

            if self.on_chapter_done:
                self.on_chapter_done(result)

        # Generate and save manifest
        manifest = generate_manifest(results, self.config, txt_path)
        save_manifest(manifest, output_dir)

        succeeded = sum(1 for r in results if r.success)
        self._log(f"Complete! Generated {succeeded} audio files")
        self._log(f"Output directory: {output_dir}")

        return results

    async def _convert_chapter(
        self,
        chapter: Chapter,
        real_chapter_num: int,
        output_dir: Path,
        temp_dir: Path,
    ) -> ConversionResult:
        """Convert a single chapter to an MP3 file.

        Handles chunk-level caching: if a temp chunk file already exists
        (from a previous interrupted run), it is reused.
        """
        start_time = time.time()
        safe_title = sanitize_filename(chapter.title)
        output_filename = f"{real_chapter_num:03d}_{safe_title}.mp3"
        output_path = output_dir / output_filename

        chunks = split_text_into_chunks(
            chapter.text, max_length=1000, chapter_index=chapter.index
        )

        if len(chunks) == 1:
            # Short chapter — synthesize, then enhance
            if output_path.exists():
                # Cache hit: already generated
                return ConversionResult(
                    chapter=chapter,
                    output_path=output_path,
                    chunks_count=1,
                    duration_s=time.time() - start_time,
                    success=True,
                )
            try:
                # Synthesize to temp file first, then enhance
                raw_path = temp_dir / f"raw_{real_chapter_num:03d}.mp3"
                await self.tts.synthesize(chunks[0].text, raw_path, self.config.voice, self.config.rate)
                if not enhance_audio(raw_path, output_path):
                    # ffmpeg not available — just move the raw file
                    raw_path.replace(output_path)
                raw_path.unlink(missing_ok=True)
                success = True
                error = None
            except Exception as exc:
                success = False
                error = str(exc)
                logger.error("TTS failed for chapter %s: %s", chapter.title, exc)

            return ConversionResult(
                chapter=chapter,
                output_path=output_path,
                chunks_count=1,
                duration_s=time.time() - start_time,
                success=success,
                error=error,
            )

        # Long chapter — synthesize chunks, then merge
        temp_files: List[Path] = []
        for j, chunk in enumerate(chunks):
            if not self._wait_if_paused():
                break
            if self._should_break():
                break

            temp_path = temp_dir / f"temp_{real_chapter_num:03d}_{j + 1:03d}.mp3"

            if self.on_chunk_start:
                self.on_chunk_start(j + 1, len(chunks), chapter.title)

            if temp_path.exists():
                # Cache hit: reuse existing temp file
                self._log(f"  Cache hit: chunk {j + 1}/{len(chunks)}")
            else:
                try:
                    await self.tts.synthesize(
                        chunk.text, temp_path, self.config.voice, self.config.rate
                    )
                except Exception as exc:
                    logger.error("TTS failed for chunk %d of %s: %s", j + 1, chapter.title, exc)
                    return ConversionResult(
                        chapter=chapter,
                        output_path=output_path,
                        chunks_count=len(temp_files),
                        duration_s=time.time() - start_time,
                        success=False,
                        error=str(exc),
                    )

            temp_files.append(temp_path)

            if self.on_chunk_done:
                self.on_chunk_done(j + 1, len(chunks))

        # Merge chunks into the final file
        if temp_files and not self._should_break():
            merge_audio_files(temp_files, output_path)
            success = True
            error = None
        else:
            success = False
            error = "Skipped or interrupted"

        return ConversionResult(
            chapter=chapter,
            output_path=output_path,
            chunks_count=len(temp_files),
            duration_s=time.time() - start_time,
            success=success,
            error=error,
        )
