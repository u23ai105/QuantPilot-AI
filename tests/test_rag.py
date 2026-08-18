from app.services.rag.text_chunker import TextChunker


def test_chunker_enforces_page_boundaries():
    chunker = TextChunker(max_chars=2000, min_chars=50)

    page_1_text = "This is a short sentence. Here is another one. And a third."
    page_2_text = "A word. " * 500

    pages = [(1, page_1_text), (2, page_2_text)]

    chunks = chunker.chunk_pages(pages)

    page_1_chunks = [c for c in chunks if c["page_number"] == 1]
    page_2_chunks = [c for c in chunks if c["page_number"] == 2]

    assert len(page_1_chunks) == 1
    assert page_1_chunks[0]["chunk_text"].replace(" ", "") == page_1_text.replace(" ", "")

    assert len(page_2_chunks) > 1
    for c in page_2_chunks:
        assert len(c["chunk_text"]) <= 2050


def test_chunker_handles_tiny_pages():
    chunker = TextChunker(max_chars=200, min_chars=50)

    pages = [(1, "A very short page."), (2, "Another slightly longer page that might pass the limit if we add more text. More text here.")]

    chunks = chunker.chunk_pages(pages)
    assert len(chunks) == 2
    assert chunks[0]["chunk_text"].replace(" ", "") == "A very short page.".replace(" ", "")
    expected = "Another slightly longer page that might pass the limit if we add more text. More text here."
    assert chunks[1]["chunk_text"].replace(" ", "") == expected.replace(" ", "")


def test_chunker_zero_overlap():
    chunker = TextChunker(max_chars=100, min_chars=10)
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    pages = [(1, text)]
    chunks = chunker.chunk_pages(pages)

    combined = " ".join([c["chunk_text"] for c in chunks])
    assert combined.replace(" ", "") == text.replace(" ", "")
