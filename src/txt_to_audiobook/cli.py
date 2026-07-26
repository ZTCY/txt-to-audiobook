"""Command-line interface for txt-to-audiobook."""

import argparse
import asyncio
import re
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

from .config import (
    DEFAULT_VOICE,
    OUTPUT_DIR,
    RECOMMENDED_VOICES,
    TXT_INPUT_DIR,
)
from .models import ConversionConfig
from .parser import clean_text, split_chapters, split_text_into_chunks
from .pipeline import AudiobookPipeline
from .tts.edge import EdgeTTSProvider


# ========== Global state for keyboard monitoring ==========

_STATE = {
    "running": True,
    "paused": False,
}


def _print_header() -> None:
    """Print the CLI banner."""
    print("=" * 60)
    print("📚 Audiobook Automation Pipeline - Edge TTS")
    print("=" * 60)
    print()


def _print_controls() -> None:
    """Print keyboard control instructions."""
    print("=" * 60)
    print("🎮 Controls:")
    print("   P - Pause / Resume")
    print("   Q - Stop (stop all conversion)")
    print("   S - Skip current chapter, move to next")
    print("=" * 60)
    print()


def _monitor_input(pipeline: AudiobookPipeline) -> None:
    """Monitor keyboard input in a background thread (CLI interactive mode)."""
    while _STATE["running"]:
        try:
            user_input = input().strip().upper()
            if user_input == "P":
                if _STATE["paused"]:
                    _STATE["paused"] = False
                    pipeline.resume()
                    print("\n▶️  [Resumed] Converting...")
                else:
                    _STATE["paused"] = True
                    pipeline.pause()
                    print("\n⏸️  [Paused] Press P to resume...")
            elif user_input == "Q":
                print("\n🛑 [Stop] Stopping all conversion...")
                _STATE["running"] = False
                pipeline.stop()
            elif user_input == "S":
                if _STATE["paused"]:
                    print("\n⚠️  [Hint] Press P to resume first, then S to skip")
                else:
                    print("\n⏭️  [Skip] Will skip current chapter...")
                    pipeline.skip_current()
        except (EOFError, KeyboardInterrupt):
            break
        except Exception:
            pass
        time.sleep(0.1)


def _list_voices() -> None:
    """Fetch and display all available Chinese voices from Edge TTS."""
    print("🔊 Fetching available voices...")
    provider = EdgeTTSProvider()
    voices = asyncio.run(provider.list_voices())
    print("\nAvailable Chinese voices:")
    print("-" * 60)
    for voice in voices:
        if voice["Locale"].startswith("zh-"):
            print(f"  {voice['ShortName']:<40} | {voice['FriendlyName']}")
    print("-" * 60)
    print()


def _run_dry_run(txt_path: Path, voice: str, rate: str,
                 start: Optional[int], end: Optional[int]) -> None:
    """Print conversion plan without actually generating audio."""
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            raw = f.read()
    except UnicodeDecodeError:
        with open(txt_path, "r", encoding="gbk") as f:
            raw = f.read()

    text = clean_text(raw)
    chapters = split_chapters(text)

    print(f"📄 File: {txt_path.name}")
    print(f"📝 Characters: {len(text)}")
    print(f"📚 Chapters detected: {len(chapters)}")

    if start or end:
        s = (start or 1) - 1
        e = end or len(chapters)
        s = max(0, s)
        e = min(len(chapters), e)
        chapters = chapters[s:e]
        print(f"📖 Will process chapters {s + 1} to {e} ({len(chapters)} chapters)")

    total_chunks = 0
    for ch in chapters:
        chunks = split_text_into_chunks(ch.text, max_length=1000)
        total_chunks += len(chunks)

    print(f"🧩 Total chunks (TTS calls): {total_chunks}")
    # Rough estimate: ~2 seconds per chunk (network + synthesis)
    est_seconds = total_chunks * 2
    print(f"⏱️  Estimated time: ~{est_seconds}s ({est_seconds // 60}m {est_seconds % 60}s)")
    print()
    print("Preview of chapters:")
    for i, ch in enumerate(chapters[:10]):
        print(f"  {i + 1}. {ch.title}")
    if len(chapters) > 10:
        print(f"  ... {len(chapters) - 10} more chapters")


def _interactive_mode(args: argparse.Namespace) -> None:
    """Run the interactive CLI (no arguments provided)."""
    _print_header()

    # Start keyboard monitor thread
    pipeline = AudiobookPipeline(
        config=ConversionConfig(),
        tts_provider=EdgeTTSProvider(),
    )
    monitor_thread = threading.Thread(target=_monitor_input, args=(pipeline,), daemon=True)
    monitor_thread.start()
    _print_controls()

    # Check input folder
    txt_input_path = Path(TXT_INPUT_DIR)
    if not txt_input_path.exists():
        print(f"❌ Error: Input folder does not exist: {TXT_INPUT_DIR}")
        return

    txt_files = sorted(txt_input_path.glob("*.txt"))
    if not txt_files:
        print(f"❌ No TXT files found in: {TXT_INPUT_DIR}")
        print("   Please place novel TXT files in this folder")
        return

    print(f"📂 Found {len(txt_files)} TXT file(s):")
    for i, f in enumerate(txt_files, 1):
        print(f"   {i}. {f.name}")
    print()

    # Voice selection
    print("🎤 Select voice (enter number):")
    for key, voice in RECOMMENDED_VOICES.items():
        print(f"   {key}. {voice}")
    print("   0. List all available voices")
    print()
    choice = input("Enter choice (default 1): ").strip() or "1"

    if choice == "0":
        _list_voices()
        choice = input("Enter choice (enter number): ").strip() or "1"

    voice = RECOMMENDED_VOICES.get(choice, RECOMMENDED_VOICES["1"])
    print(f"✅ Selected voice: {voice}")
    print()

    rate = input("⚡ Rate adjustment (default +0%, e.g. +10% or -10%): ").strip() or "+0%"
    print()

    # Chapter range
    print("📚 Chapter range:")
    print("   1. All chapters")
    print("   2. Specific range (e.g. 20-32)")
    print()
    range_choice = input("Enter choice (default 1): ").strip() or "1"

    start_chapter: Optional[int] = None
    end_chapter: Optional[int] = None

    if range_choice == "2":
        range_input = input("Enter chapter range (format: start-end, e.g. 20-32): ").strip()
        try:
            match = re.match(r"(\d+)-(\d+)", range_input)
            if match:
                start_chapter = int(match.group(1))
                end_chapter = int(match.group(2))
                if start_chapter > end_chapter:
                    print("❌ Error: Start chapter cannot be greater than end chapter")
                    return
                print(f"✅ Will convert chapters {start_chapter} to {end_chapter}")
            else:
                print("❌ Invalid format, will convert all chapters")
        except ValueError:
            print("❌ Invalid input, will convert all chapters")
    else:
        print("✅ Will convert all chapters")
    print()

    # Build config
    config = ConversionConfig(
        voice=voice,
        rate=rate,
        output_dir=Path(OUTPUT_DIR),
        start_chapter=start_chapter,
        end_chapter=end_chapter,
    )
    pipeline.config = config

    # Process files
    for txt_file in txt_files:
        if not _STATE["running"]:
            break
        _STATE["paused"] = False
        pipeline.resume()

        pipeline.on_log = lambda msg: print(msg)

        asyncio.run(pipeline.convert(txt_file))

    _STATE["running"] = False
    print()
    print("=" * 60)
    if _STATE["running"]:
        print("🎉 All files processed!")
    else:
        print("⚠️  Processing terminated")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print("=" * 60)


def _cli_mode(args: argparse.Namespace) -> None:
    """Run with CLI arguments (non-interactive)."""
    txt_path = Path(args.input)

    if not txt_path.exists():
        print(f"❌ Error: File not found: {txt_path}")
        sys.exit(1)

    voice = args.voice or DEFAULT_VOICE
    rate = args.rate or "+0%"
    output_dir = Path(args.output) if args.output else Path(OUTPUT_DIR)

    if args.dry_run:
        _run_dry_run(txt_path, voice, rate, args.start, args.end)
        return

    config = ConversionConfig(
        voice=voice,
        rate=rate,
        output_dir=output_dir,
        start_chapter=args.start,
        end_chapter=args.end,
    )

    pipeline = AudiobookPipeline(config=config, tts_provider=EdgeTTSProvider())
    pipeline.on_log = lambda msg: print(msg)

    # Start keyboard monitor thread
    monitor_thread = threading.Thread(target=_monitor_input, args=(pipeline,), daemon=True)
    monitor_thread.start()
    _print_controls()

    asyncio.run(pipeline.convert(txt_path))

    _STATE["running"] = False


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse argument parser."""
    parser = argparse.ArgumentParser(
        prog="txt2audio",
        description="📚 Convert TXT novels to MP3 audiobooks using Edge TTS.",
    )
    parser.add_argument(
        "-i", "--input",
        help="Path to the input TXT file. If omitted, enters interactive mode.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--voice",
        help="Edge TTS voice short name (e.g. zh-CN-YunxiNeural)",
    )
    parser.add_argument(
        "--rate",
        help='Rate adjustment (e.g. +0%%, -10%%, +20%%)',
    )
    parser.add_argument(
        "--start",
        type=int,
        help="Start chapter number (1-based)",
    )
    parser.add_argument(
        "--end",
        type=int,
        help="End chapter number (inclusive)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show conversion plan without generating audio",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List all available Chinese voices",
    )
    return parser


def main() -> None:
    """Entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.list_voices:
        _list_voices()
        return

    if args.input:
        _cli_mode(args)
    else:
        _interactive_mode(args)


if __name__ == "__main__":
    main()
