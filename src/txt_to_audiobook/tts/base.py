"""Abstract TTS provider interface."""

from abc import ABC, abstractmethod
from pathlib import Path


class TTSProvider(ABC):
    """Abstract base class for text-to-speech providers."""

    @abstractmethod
    async def synthesize(self, text: str, output_path: Path, voice: str, rate: str) -> None:
        """Synthesize text to an audio file.

        Args:
            text: The text to synthesize.
            output_path: Path to save the audio file.
            voice: The voice identifier to use.
            rate: Rate adjustment string (e.g. "+0%", "-10%").
        """
        ...

    @abstractmethod
    async def list_voices(self) -> list:
        """List available voices from the provider.

        Returns:
            A list of voice dictionaries.
        """
        ...
