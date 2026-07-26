"""Audio export: merging, manifest generation, and persistence."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from .models import ConversionConfig, ConversionResult

logger = logging.getLogger(__name__)


def merge_audio_files(temp_files: List[Path], output_path: Path) -> None:
    """Concatenate multiple MP3 files into one and delete the temp files.

    Args:
        temp_files: List of temporary MP3 file paths to merge.
        output_path: Destination path for the merged file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as merged:
        for temp_file in temp_files:
            try:
                with open(temp_file, "rb") as f:
                    merged.write(f.read())
            except Exception as exc:
                logger.warning("Failed to read temp file %s: %s", temp_file, exc)

    # Clean up temporary files
    for temp_file in temp_files:
        try:
            Path(temp_file).unlink()
        except Exception:
            pass


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
