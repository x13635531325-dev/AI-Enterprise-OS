from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    content: str
    start_offset: int
    end_offset: int


class TextChunker:
    def __init__(self, max_chars: int = 800, overlap_chars: int = 120):
        if max_chars <= 0:
            raise ValueError("max_chars must be greater than zero.")

        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be between 0 and max_chars.")

        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def split(self, text: str) -> list[TextChunk]:
        normalized_text = text.strip()

        if not normalized_text:
            return []

        chunks = []
        start = 0

        while start < len(normalized_text):
            end = min(start + self.max_chars, len(normalized_text))

            if end < len(normalized_text):
                end = self._find_boundary(normalized_text, start, end)

            content = normalized_text[start:end].strip()

            if content:
                chunks.append(
                    TextChunk(
                        content=content,
                        start_offset=start,
                        end_offset=end,
                    )
                )

            if end >= len(normalized_text):
                break

            start = max(start + 1, end - self.overlap_chars)

        return chunks

    def _find_boundary(self, text: str, start: int, end: int) -> int:
        minimum_boundary = start + self.max_chars // 2
        candidates = [
            text.rfind(separator, minimum_boundary, end)
            for separator in ("\n\n", "\n", "。", "！", "？", ". ", "! ", "? ")
        ]
        boundary = max(candidates)

        if boundary == -1:
            return end

        return boundary + 1
