import re


class TextChunker:
    """Chunks text while strictly respecting page boundaries."""

    def __init__(self, max_chars: int = 2000, min_chars: int = 50):
        self.max_chars = max_chars
        self.min_chars = min_chars

    def chunk_pages(self, pages: list[tuple[int, str]]) -> list[dict]:
        """Chunks a list of (page_number, text) tuples.

        Returns a list of dicts:
        {
            "page_number": int,
            "chunk_index": int,
            "chunk_text": str
        }
        """
        all_chunks = []

        for page_num, text in pages:
            # Clean up whitespace
            text = re.sub(r"\s+", " ", text).strip()

            if len(text) < self.min_chars:
                # If the entire page is too small, just keep it as one chunk if it has any meat,
                # else skip entirely to avoid noisy small chunks.
                if len(text.strip()) > 10:  # arbitrary threshold to keep tiny but not completely empty pages
                    all_chunks.append({"page_number": page_num, "chunk_index": 0, "chunk_text": text})
                continue

            page_chunks = self._chunk_text(text)

            for idx, chunk_text in enumerate(page_chunks):
                if len(chunk_text) >= self.min_chars or (idx == len(page_chunks) - 1 and len(chunk_text) > 10):
                    all_chunks.append({"page_number": page_num, "chunk_index": idx, "chunk_text": chunk_text})

        return all_chunks

    def _chunk_text(self, text: str) -> list[str]:
        """Simple splitting by sentences/paragraphs to approach max_chars."""
        # Split by typical paragraph/sentence boundaries (periods followed by space)
        # Avoid adding double dots
        raw_sentences = [s.strip() for s in text.split(". ") if s.strip()]
        sentences = [s + "." if not s.endswith(".") else s for s in raw_sentences]

        chunks = []
        current_chunk = []
        current_len = 0

        for sentence in sentences:
            if current_len + len(sentence) > self.max_chars and current_len > 0:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_len = len(sentence) + 1
            else:
                current_chunk.append(sentence)
                current_len += len(sentence) + 1

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks
