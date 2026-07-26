"""Edge TTS provider implementation with retry logic."""

import asyncio
import logging
from pathlib import Path
from typing import List

import edge_tts

from .base import TTSProvider

logger = logging.getLogger(__name__)


class EdgeTTSProvider(TTSProvider):
    """TTS provider using Microsoft Edge TTS (free, no API key required)."""

    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds

    async def synthesize(self, text: str, output_path: Path, voice: str, rate: str) -> None:
        """Synthesize text to an MP3 file via Edge TTS, with retry.

        Retries up to MAX_RETRIES times with exponential backoff.

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
        """List all available Edge TTS voices.

        Returns:
            A list of voice dictionaries as returned by edge_tts.
        """
        return await edge_tts.list_voices()
