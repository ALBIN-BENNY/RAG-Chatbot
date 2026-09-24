import re
from dataclasses import dataclass
from typing import List
from app.core.config import settings


@dataclass
class TextChunk:
    text: str
    chunk_index: int
    page_url: str
    page_title: str
    metadata: dict


class SemanticChunker:
    """
    Splits text into semantically meaningful chunks with overlap.
    Respects heading boundaries and paragraph breaks.
    """

    def __init__(
        self,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _split_by_headers(self, text: str) -> List[str]:
        """Split at markdown-style headers first."""
        sections = re.split(r"\n(?=#{1,3} )", text)
        return [s.strip() for s in sections if s.strip()]

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
        return [s.strip() for s in sentences if s.strip()]

    def chunk(self, text: str, page_url: str, page_title: str) -> List[TextChunk]:
        """Produce overlapping chunks from a page's text."""
        if not text or len(text) < 50:
            return []

        sections = self._split_by_headers(text)
        chunks: List[TextChunk] = []
        chunk_index = 0
        carry_over = ""  # overlap text from previous chunk

        for section in sections:
            # Each section may be large; split into sentence groups
            sentences = self._split_into_sentences(section)
            buffer = carry_over
            carry_over = ""

            for sentence in sentences:
                candidate = (buffer + " " + sentence).strip() if buffer else sentence
                if len(candidate) <= self.chunk_size:
                    buffer = candidate
                else:
                    # Buffer is full — emit it
                    if buffer:
                        chunks.append(TextChunk(
                            text=buffer,
                            chunk_index=chunk_index,
                            page_url=page_url,
                            page_title=page_title,
                            metadata={"section": self._extract_header(buffer)},
                        ))
                        chunk_index += 1
                        # Keep tail as overlap
                        words = buffer.split()
                        overlap_words = words[-self.chunk_overlap // 6:] if words else []
                        carry_over = " ".join(overlap_words)
                    buffer = (carry_over + " " + sentence).strip() if carry_over else sentence
                    carry_over = ""

            if buffer and len(buffer) >= 50:
                chunks.append(TextChunk(
                    text=buffer,
                    chunk_index=chunk_index,
                    page_url=page_url,
                    page_title=page_title,
                    metadata={"section": self._extract_header(buffer)},
                ))
                chunk_index += 1
                words = buffer.split()
                carry_over = " ".join(words[-self.chunk_overlap // 6:]) if words else ""

        return chunks

    def _extract_header(self, text: str) -> str:
        m = re.match(r"#{1,3}\s+(.+)", text)
        return m.group(1) if m else ""
