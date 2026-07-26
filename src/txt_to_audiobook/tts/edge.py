"""Edge TTS provider implementation with retry logic.

Patches edge_tts to use 96kbps instead of the default 48kbps for
better audio quality. The patch modifies the installed package files
on disk and reloads the modules so the change takes effect immediately.
"""

import asyncio
import importlib
import logging
from pathlib import Path
from typing import List

import edge_tts
import edge_tts.constants as _const
import edge_tts.communicate as _comm

from .base import TTSProvider

logger = logging.getLogger(__name__)

_HIGH_BITRATE = 96_000
_LOW_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
_HIGH_FORMAT = "audio-24khz-96kbitrate-mono-mp3"


def _apply_quality_patch() -> None:
    """Patch edge_tts to use 96kbps on disk, then reload all modules."""

    # 1. Patch constants.py on disk
    const_file = Path(_const.__file__)
    text = const_file.read_text(encoding="utf-8")
    changed = False
    if "MP3_BITRATE_BPS = 48_000" in text:
        text = text.replace("MP3_BITRATE_BPS = 48_000", "MP3_BITRATE_BPS = 96_000")
        changed = True
    if "MP3_BITRATE_BPS = 48000" in text:
        text = text.replace("MP3_BITRATE_BPS = 48000", "MP3_BITRATE_BPS = 96000")
        changed = True
    if changed:
        const_file.write_text(text, encoding="utf-8")
        logger.info("edge_tts: patched constants.py -> 96kbps")

    # 2. Patch communicate.py on disk
    comm_file = Path(_comm.__file__)
    text = comm_file.read_text(encoding="utf-8")
    if _LOW_FORMAT in text:
        text = text.replace(_LOW_FORMAT, _HIGH_FORMAT)
        comm_file.write_text(text, encoding="utf-8")
        changed = True
        logger.info("edge_tts: patched communicate.py -> 96kbps")

    # 3. Reload modules so in-memory code picks up the patched source.
    #    Order matters: reload constants first, then communicate, then top-level.
    importlib.reload(_const)
    importlib.reload(_comm)
    importlib.reload(edge_tts)

    # 4. Sanity check
    if _const.MP3_BITRATE_BPS != _HIGH_BITRATE:
        _const.MP3_BITRATE_BPS = _HIGH_BITRATE
        logger.warning("edge_tts: had to force MP3_BITRATE_BPS in-memory")

    logger.info("edge_tts: quality patch applied (96kbps)")


# Apply patch on import
try:
    _apply_quality_patch()
except Exception as e:
    logger.warning("Failed to patch edge_tts bitrate (using default 48kbps): %s", e)


class EdgeTTSProvider(TTSProvider):
    """TTS provider using Microsoft Edge TTS (free, no API key required).

    Audio quality is 96kbps (patched at import time) instead of the
    default 48kbps for clearer narration.
    """

    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds

    async def synthesize(self, text: str, output_path: Path, voice: str, rate: str) -> None:
        """Synthesize text to an MP3 file via Edge TTS, with retry.

        Args:
            text: The text to synthesize.
            output_path: Path to save the audio file.
            voice: Edge TTS voice short name (e.g. "zh-CN-YunxiNeural").
            rate: Rate adjustment (e.g. "+0%", "-10%").

        Raises:
            RuntimeError: If all retry attempts fail.
        """
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                communicate = edge_tts.Communicate(text, voice, rate=rate)
                await communicate.save(str(output_path))
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "TTS attempt %d/%d failed for voice=%s: %s",
                    attempt, self.MAX_RETRIES, voice, exc,
                )
                if attempt < self.MAX_RETRIES:
                    delay = self.BASE_DELAY * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"Edge TTS failed after {self.MAX_RETRIES} attempts: {last_error}"
        ) from last_error

    async def list_voices(self) -> List[dict]:
        """List all available Edge TTS voices."""
        return await edge_tts.list_voices()
