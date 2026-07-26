"""Audio export: merging, manifest generation, and persistence."""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List

from .models import ConversionConfig, ConversionResult

logger = logging.getLogger(__name__)


def _ffmpeg_available() -> bool:
    """Check if ffmpeg is on PATH."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def enhance_audio(input_path: Path, output_path: Path) -> bool:
    """Use ffmpeg to upsample to 48kHz, 320kbps, and normalize loudness.

    This significantly improves playback quality on most devices by:
    - Upsampling 24kHz → 48kHz (avoids player resampling artifacts)
    - Increasing bitrate 96kbps → 320kbps (eliminates compression artifacts)
    - Applying EBU R128 loudness normalization (consistent volume)

    Args:
        input_path: Source MP3 (edge-tts output, 96kbps/24kHz).
        output_path: Destination MP3 (enhanced).

    Returns:
        True if enhancement succeeded, False if ffmpeg unavailable or failed.
    """
    if not _ffmpeg_available():
        logger.warning("ffmpeg not found, skipping audio enhancement")
        return False

    tmp = output_path.with_suffix(".tmp.mp3")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(input_path),
                "-ar", "48000",           # sample rate: 48kHz
                "-b:a", "320k",            # bitrate: 320kbps
                "-af", "loudnorm=I=-16:LRA=11:TP=-1.5,volume=0.8",  # EBU R128 normalization
                "-codec:a", "libmp3lame",  # use LAME encoder
                "-q:a", "0",               # highest quality
                str(tmp),
            ],
            capture_output=True, timeout=120,
        )
        if tmp.exists() and tmp.stat().st_size > 0:
            tmp.replace(output_path)
            return True
        else:
            logger.warning("ffmpeg produced empty output, keeping original")
            tmp.unlink(missing_ok=True)
            return False
    except Exception as exc:
        logger.warning("ffmpeg enhancement failed: %s", exc)
        tmp.unlink(missing_ok=True)
        return False


def merge_audio_files(temp_files: List[Path], output_path: Path) -> None:
    """Concatenate multiple MP3 files, enhance, and delete temp files.

    Uses ffmpeg for proper stream copying + loudness normalization when
    available; falls back to binary concatenation if ffmpeg is missing.

    Args:
        temp_files: List of temporary MP3 file paths to merge.
        output_path: Destination path for the merged file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if _ffmpeg_available() and len(temp_files) > 1:
        # Use ffmpeg concat demuxer for gapless merging
        list_path = output_path.parent / f".{output_path.stem}_concat.txt"
        try:
            list_path.write_text(
                "\n".join(f"file '{f.resolve()}'" for f in temp_files),
                encoding="utf-8",
            )
            tmp_merged = output_path.with_suffix(".raw.mp3")
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(list_path),
                    "-c", "copy",
                    str(tmp_merged),
                ],
                capture_output=True, timeout=120,
            )
            list_path.unlink(missing_ok=True)

            if tmp_merged.exists() and tmp_merged.stat().st_size > 0:
                # Enhance the merged file
                if enhance_audio(tmp_merged, output_path):
                    tmp_merged.unlink(missing_ok=True)
                else:
                    tmp_merged.replace(output_path)
            else:
                # ffmpeg concat failed, fall back to binary merge
                logger.warning("ffmpeg concat failed, using binary merge")
                _binary_merge(temp_files, output_path)
        except Exception as exc:
            logger.warning("ffmpeg merge failed: %s, using binary merge", exc)
            list_path.unlink(missing_ok=True)
            _binary_merge(temp_files, output_path)
    elif _ffmpeg_available() and len(temp_files) == 1:
        # Single chunk — just enhance
        if not enhance_audio(temp_files[0], output_path):
            _binary_merge(temp_files, output_path)
    else:
        _binary_merge(temp_files, output_path)

    # Clean up temporary files
    for temp_file in temp_files:
        try:
            Path(temp_file).unlink()
        except Exception:
            pass


def _binary_merge(temp_files: List[Path], output_path: Path) -> None:
    """Fallback: simple binary concatenation of MP3 files."""
    with open(output_path, "wb") as merged:
        for temp_file in temp_files:
            try:
                with open(temp_file, "rb") as f:
                    merged.write(f.read())
            except Exception as exc:
                logger.warning("Failed to read temp file %s: %s", temp_file, exc)


def generate_manifest(
    results: List[ConversionResult],
    config: ConversionConfig,
    txt_path: Path,
) -> dict:
    """Build a manifest dict summarizing a conversion run.

    Args:
        results: List of per-chapter conversion results.
        config: The conversion configuration used.
        txt_path: Path to the source TXT file.

    Returns:
        A JSON-serializable manifest dictionary.
    """
    total_duration = sum(r.duration_s for r in results)
    succeeded = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    return {
        "source_file": str(txt_path),
        "source_filename": txt_path.name,
        "generated_at": datetime.now().isoformat(),
        "config": {
            "voice": config.voice,
            "rate": config.rate,
            "output_dir": str(config.output_dir),
            "start_chapter": config.start_chapter,
            "end_chapter": config.end_chapter,
        },
        "summary": {
            "total_chapters": len(results),
            "succeeded": len(succeeded),
            "failed": len(failed),
            "total_duration_s": round(total_duration, 2),
        },
        "chapters": [
            {
                "index": r.chapter.index,
                "title": r.chapter.title,
                "output_path": str(r.output_path),
                "chunks_count": r.chunks_count,
                "duration_s": round(r.duration_s, 2),
                "success": r.success,
                "error": r.error,
            }
            for r in results
        ],
    }


def save_manifest(manifest: dict, output_dir: Path) -> Path:
    """Write the manifest dict as manifest.json in the output directory.

    Args:
        manifest: The manifest dictionary to save.
        output_dir: Directory to write the file into.

    Returns:
        The path to the written manifest.json file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest_path
