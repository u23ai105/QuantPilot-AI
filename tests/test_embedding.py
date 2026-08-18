from unittest.mock import AsyncMock, patch

import pytest

from app.ai.embedding import GeminiEmbeddingAdapter


@pytest.mark.asyncio
@patch("app.ai.embedding.settings.gemini_api_key", "fake-key-for-tests")
@patch("langchain_google_genai.GoogleGenerativeAIEmbeddings.aembed_documents", new_callable=AsyncMock)
@patch("langchain_google_genai.GoogleGenerativeAIEmbeddings.aembed_query", new_callable=AsyncMock)
async def test_embedding_adapter_dimension_validation(mock_query, mock_docs):
    adapter = GeminiEmbeddingAdapter()

    # Mock to return a valid 768-dimension vector
    valid_vector = [0.1] * 768
    mock_docs.return_value = [valid_vector]

    res = await adapter.embed_documents(["test"])
    assert len(res[0]) == 768

    # Mock to return an invalid 1536-dimension vector
    invalid_vector = [0.1] * 1536
    mock_docs.return_value = [invalid_vector]

    with pytest.raises(ValueError, match="Invalid embedding dimension"):
        await adapter.embed_documents(["test"])

    # Test query validation
    mock_query.return_value = valid_vector
    res_q = await adapter.embed_query("test")
    assert len(res_q) == 768

    mock_query.return_value = invalid_vector
    with pytest.raises(ValueError, match="Invalid embedding dimension"):
        await adapter.embed_query("test")
