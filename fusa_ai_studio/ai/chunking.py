from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    index: int
    content: str
    metadata: dict


class ChunkingEngine:
    def chunk(self, text: str, strategy: str = "section", chunk_size: int = 900, overlap: int = 120) -> list[Chunk]:
        normalized = re.sub(r"\n{3,}", "\n\n", text.strip())
        if not normalized:
            return []
        if strategy == "fixed":
            return self._fixed(normalized, chunk_size, overlap)
        if strategy == "recursive":
            return self._recursive(normalized, chunk_size, overlap)
        return self._section(normalized, chunk_size, overlap)

    def _fixed(self, text: str, chunk_size: int, overlap: int) -> list[Chunk]:
        chunks: list[Chunk] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(Chunk(len(chunks), text[start:end].strip(), {"strategy": "fixed"}))
            if end == len(text):
                break
            start = max(0, end - overlap)
        return [chunk for chunk in chunks if chunk.content]

    def _recursive(self, text: str, chunk_size: int, overlap: int) -> list[Chunk]:
        paragraphs = text.split("\n\n")
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(paragraph) > chunk_size:
                    chunks.extend(chunk.content for chunk in self._fixed(paragraph, chunk_size, overlap))
                    current = ""
                else:
                    current = paragraph
        if current:
            chunks.append(current)
        return [Chunk(i, content, {"strategy": "recursive"}) for i, content in enumerate(chunks) if content.strip()]

    def _section(self, text: str, chunk_size: int, overlap: int) -> list[Chunk]:
        sections = re.split(r"(?=^#{1,3}\s+)", text, flags=re.MULTILINE)
        chunks: list[Chunk] = []
        for section in [part.strip() for part in sections if part.strip()]:
            heading_match = re.match(r"^(#{1,3}\s+.+)$", section)
            heading = heading_match.group(1).replace("#", "").strip() if heading_match else "Untitled section"
            if len(section) <= chunk_size:
                chunks.append(Chunk(len(chunks), section, {"strategy": "section", "section": heading}))
            else:
                for chunk in self._recursive(section, chunk_size, overlap):
                    chunks.append(Chunk(len(chunks), chunk.content, {"strategy": "section", "section": heading}))
        return chunks
