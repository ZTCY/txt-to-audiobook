"""Text parsing: cleaning, chapter detection, chunking, filename sanitization."""

import re
from typing import List

from .models import Chapter, Chunk


def clean_text(text: str) -> str:
    """Remove BOM, normalize newlines, and collapse excessive blank lines.

    Args:
        text: Raw text read from a TXT file.

    Returns:
        Cleaned text.
    """
    # Remove BOM if present
    if text.startswith("\ufeff"):
        text = text[1:]

    # Normalize line endings: \r\n and \r -> \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse 3+ consecutive newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def split_chapters(text: str) -> List[Chapter]:
    """Detect chapter boundaries and split text into chapters.

    Supports patterns: 第X章, 第X回, Chapter X, 第X节.

    Args:
        text: The full (preferably cleaned) text.

    Returns:
        A list of Chapter objects. If no chapter markers are found,
        returns a single chapter containing the entire text.
    """
    chapter_patterns = [
        r"第[一二三四五六七八九十百千\d]+章",
        r"第[一二三四五六七八九十百千\d]+回",
        r"Chapter\s+\d+",
        r"第\d+节",
    ]

    pattern = "|".join(chapter_patterns)
    matches = list(re.finditer(pattern, text))

    if not matches:
        return [Chapter(title="Full Text", text=text, index=0)]

    chapters: List[Chapter] = []
    for i, match in enumerate(matches):
        title = match.group().strip()
        start = match.start()

        if i < len(matches) - 1:
            end = matches[i + 1].start()
        else:
            end = len(text)

        chapter_text = text[start:end].strip()
        chapters.append(Chapter(title=title, text=chapter_text, index=i))

    return chapters


def split_text_into_chunks(text: str, max_length: int = 1000, chapter_index: int = 0) -> List[Chunk]:
    """Split long text into chunks at sentence boundaries.

    TTS APIs typically have a length limit per request. This function
    breaks text at punctuation marks to stay within the limit.

    Args:
        text: The text to chunk.
        max_length: Maximum characters per chunk (default 1000).
        chapter_index: Index of the parent chapter (for tracking).

    Returns:
        A list of Chunk objects.
    """
    if len(text) <= max_length:
        return [Chunk(text=text, index=0, chapter_index=chapter_index)]

    chunks: List[Chunk] = []
    current_chunk = ""
    sentence_endings = ["。", "！", "？", "…", "\n", ".", "!", "?"]
    chunk_index = 0

    for char in text:
        current_chunk += char

        if len(current_chunk) >= max_length:
            # Find the last sentence-ending punctuation
            last_punct = -1
            for p in sentence_endings:
                pos = current_chunk.rfind(p)
                if pos > last_punct:
                    last_punct = pos

            if last_punct > 0:
                chunks.append(Chunk(
                    text=current_chunk[: last_punct + 1],
                    index=chunk_index,
                    chapter_index=chapter_index,
                ))
                current_chunk = current_chunk[last_punct + 1:]
            else:
                chunks.append(Chunk(
                    text=current_chunk,
                    index=chunk_index,
                    chapter_index=chapter_index,
                ))
                current_chunk = ""

            chunk_index += 1

    if current_chunk:
        chunks.append(Chunk(
            text=current_chunk,
            index=chunk_index,
            chapter_index=chapter_index,
        ))

    return chunks


def sanitize_filename(title: str, max_length: int = 50) -> str:
    """Remove characters that are illegal in filenames on Windows.

    Args:
        title: The raw title string.
        max_length: Maximum length of the result (default 50).

    Returns:
        A safe filename component.
    """
    return re.sub(r'[\\/*?:"<>|]', "", title)[:max_length]
