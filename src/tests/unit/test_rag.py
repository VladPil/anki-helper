"""Unit tests for RAG (Retrieval Augmented Generation) service.

Tests cover:
- Embedding generation via SOP_LLM
- Caching functionality
- Similarity calculation
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.rag.embeddings import EmbeddingService

from src.tests.fixtures.sample_data import (
    SAMPLE_DOCUMENTS,
    SAMPLE_EMBEDDINGS,
)


# ==================== Embedding Service Tests ====================


@pytest.mark.asyncio
class TestEmbeddingService:
    """Tests for the embedding service."""

    async def test_service_initialization(self, mock_redis):
        """Test service initialization."""
        service = EmbeddingService(redis=mock_redis)

        assert service._redis is mock_redis

    async def test_service_initialization_without_redis(self):
        """Test service initialization without Redis."""
        service = EmbeddingService(redis=None)

        assert service._redis is None

    async def test_cache_key_generation(self, mock_redis):
        """Test cache key generation."""
        service = EmbeddingService(redis=mock_redis)

        key1 = service._get_cache_key("text1", "model1")
        key2 = service._get_cache_key("text2", "model1")
        key3 = service._get_cache_key("text1", "model2")

        # Same text, same model = same key
        assert service._get_cache_key("text1", "model1") == key1

        # Different text or model = different key
        assert key1 != key2
        assert key1 != key3

    async def test_cache_key_format(self, mock_redis):
        """Test cache key format."""
        service = EmbeddingService(redis=mock_redis)

        key = service._get_cache_key("test text", "test-model")

        assert key.startswith("emb:")
        assert "test-model" in key

    async def test_embed_empty_list(self, mock_redis):
        """Test embedding empty list."""
        service = EmbeddingService(redis=mock_redis)

        embeddings = await service.embed([])

        assert embeddings == []

    async def test_embed_success_with_mocked_llm(self, mock_redis):
        """Test successful embedding via mocked LLM client."""
        service = EmbeddingService(redis=None)  # No cache

        with patch("src.rag.embeddings.get_llm_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.generate_embeddings = AsyncMock(return_value=[
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
            ])
            mock_get_client.return_value = mock_client

            result = await service.embed(["Hello", "World"], use_cache=False)

            assert len(result) == 2
            assert result[0] == [0.1, 0.2, 0.3]
            assert result[1] == [0.4, 0.5, 0.6]

    async def test_embed_with_cache_hit(self, mock_redis):
        """Test embedding with cache hit."""
        # Setup cache to return cached embeddings
        cached_embedding = [0.1, 0.2, 0.3]
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[
            json.dumps(cached_embedding),
        ])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        service = EmbeddingService(redis=mock_redis)

        result = await service.embed(["Hello"], use_cache=True)

        assert len(result) == 1
        assert result[0] == cached_embedding

    async def test_embed_with_partial_cache_hit(self, mock_redis):
        """Test embedding with partial cache hit."""
        cached_embedding = [0.1, 0.2, 0.3]
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[
            json.dumps(cached_embedding),  # First text cached
            None,  # Second text not cached
        ])
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        service = EmbeddingService(redis=mock_redis)

        with patch("src.rag.embeddings.get_llm_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.generate_embeddings = AsyncMock(return_value=[
                [0.4, 0.5, 0.6],  # Only uncached text
            ])
            mock_get_client.return_value = mock_client

            result = await service.embed(["Hello", "World"], use_cache=True)

            assert len(result) == 2
            assert result[0] == cached_embedding
            assert result[1] == [0.4, 0.5, 0.6]

    async def test_embed_single(self, mock_redis):
        """Test embedding single text."""
        service = EmbeddingService(redis=None)

        with patch.object(service, "embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [[0.1, 0.2, 0.3]]

            result = await service.embed_single("Hello")

            assert result == [0.1, 0.2, 0.3]
            mock_embed.assert_called_once_with(
                ["Hello"],
                use_cache=True,
                model_name=None,
            )

    async def test_calculate_similarity(self, mock_redis):
        """Test similarity calculation."""
        service = EmbeddingService(redis=mock_redis)

        with patch("src.rag.embeddings.get_llm_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.calculate_similarity = AsyncMock(return_value=0.85)
            mock_get_client.return_value = mock_client

            result = await service.calculate_similarity("Hello", "Hi")

            assert result == 0.85

    def test_dimension_property(self, mock_redis):
        """Test dimension property."""
        service = EmbeddingService(redis=mock_redis)

        # Should return config value
        assert service.dimension > 0

    def test_model_name_property(self, mock_redis):
        """Test model_name property."""
        service = EmbeddingService(redis=mock_redis)

        assert service.model_name is not None

    async def test_close(self, mock_redis):
        """Test close method."""
        service = EmbeddingService(redis=mock_redis)

        # Should not raise
        await service.close()


# ==================== Similarity Search Tests ====================


class TestSimilaritySearch:
    """Tests for similarity search functionality."""

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        import math

        def cosine_similarity(a: list[float], b: list[float]) -> float:
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot_product / (norm_a * norm_b)

        # Identical vectors
        vec = [1.0, 0.0, 0.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

        # Orthogonal vectors
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(0.0)

        # Opposite vectors
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [-1.0, 0.0, 0.0]
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(-1.0)

    def test_euclidean_distance(self):
        """Test Euclidean distance calculation."""
        import math

        def euclidean_distance(a: list[float], b: list[float]) -> float:
            return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

        # Same point
        vec = [1.0, 2.0, 3.0]
        assert euclidean_distance(vec, vec) == 0.0

        # Unit distance
        vec_a = [0.0, 0.0, 0.0]
        vec_b = [1.0, 0.0, 0.0]
        assert euclidean_distance(vec_a, vec_b) == 1.0

    def test_top_k_selection(self):
        """Test selecting top-k most similar results."""
        scores = [
            (0, 0.95),
            (1, 0.80),
            (2, 0.75),
            (3, 0.90),
            (4, 0.60),
        ]

        # Sort by score descending
        sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)

        # Get top 3
        top_3 = sorted_scores[:3]

        assert top_3[0] == (0, 0.95)
        assert top_3[1] == (3, 0.90)
        assert top_3[2] == (1, 0.80)

    def test_score_threshold_filtering(self):
        """Test filtering results by minimum score threshold."""
        results = [
            {"id": 1, "score": 0.95},
            {"id": 2, "score": 0.70},
            {"id": 3, "score": 0.55},
            {"id": 4, "score": 0.40},
        ]

        threshold = 0.60
        filtered = [r for r in results if r["score"] >= threshold]

        assert len(filtered) == 2
        assert all(r["score"] >= threshold for r in filtered)


# ==================== Document Processing Tests ====================


class TestDocumentProcessing:
    """Tests for document processing and chunking."""

    def test_simple_text_chunking(self):
        """Test simple text chunking by character count."""
        def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
            chunks = []
            start = 0
            while start < len(text):
                end = start + chunk_size
                chunks.append(text[start:end])
                start += chunk_size - overlap
            return chunks

        text = "A" * 1000
        chunks = chunk_text(text, chunk_size=200, overlap=50)

        assert all(len(c) <= 200 for c in chunks)
        assert len(chunks) > 1

    def test_sentence_based_chunking(self):
        """Test chunking by sentences."""
        def chunk_by_sentences(
            text: str,
            max_sentences: int = 5,
        ) -> list[str]:
            sentences = text.split(". ")
            chunks = []
            for i in range(0, len(sentences), max_sentences):
                chunk = ". ".join(sentences[i:i + max_sentences])
                if not chunk.endswith("."):
                    chunk += "."
                chunks.append(chunk)
            return chunks

        text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five. Sentence six. Sentence seven."
        chunks = chunk_by_sentences(text, max_sentences=3)

        assert len(chunks) == 3

    def test_metadata_preservation(self):
        """Test that metadata is preserved during processing."""
        document = SAMPLE_DOCUMENTS[0]

        processed = {
            "content": document["content"][:100],  # Truncated
            "metadata": document["metadata"].copy(),
            "chunk_index": 0,
        }

        assert processed["metadata"]["source"] == document["metadata"]["source"]
        assert processed["metadata"]["page"] == document["metadata"]["page"]


# ==================== Context Building Tests ====================


class TestContextBuilding:
    """Tests for building context for generation."""

    def test_build_context_from_documents(self):
        """Test building context string from retrieved documents."""
        documents = SAMPLE_DOCUMENTS[:2]

        context_parts = []
        for i, doc in enumerate(documents, 1):
            part = f"[{i}] {doc['content']}"
            context_parts.append(part)

        context = "\n\n".join(context_parts)

        assert "[1]" in context
        assert "[2]" in context
        assert documents[0]["content"] in context

    def test_context_truncation(self):
        """Test truncating context to max length."""
        def truncate_context(context: str, max_length: int) -> str:
            if len(context) <= max_length:
                return context
            # Truncate at last sentence boundary
            truncated = context[:max_length]
            last_period = truncated.rfind(".")
            if last_period > max_length // 2:
                return truncated[:last_period + 1]
            return truncated + "..."

        long_context = "A" * 1000 + ". " + "B" * 1000
        truncated = truncate_context(long_context, max_length=500)

        assert len(truncated) <= 503  # 500 + "..."

    def test_context_deduplication(self):
        """Test removing duplicate content from context."""
        documents = [
            {"content": "Unique content A"},
            {"content": "Duplicate content"},
            {"content": "Duplicate content"},
            {"content": "Unique content B"},
        ]

        seen_content = set()
        unique_docs = []
        for doc in documents:
            if doc["content"] not in seen_content:
                seen_content.add(doc["content"])
                unique_docs.append(doc)

        assert len(unique_docs) == 3


# ==================== Error Handling Tests ====================


@pytest.mark.asyncio
class TestRAGErrorHandling:
    """Tests for RAG error handling."""

    async def test_handle_embedding_error(self, mock_redis):
        """Test handling embedding generation errors."""
        service = EmbeddingService(redis=None)

        with patch("src.rag.embeddings.get_llm_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.generate_embeddings = AsyncMock(
                side_effect=RuntimeError("Embedding service unavailable")
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(RuntimeError) as exc_info:
                await service.embed(["Test"], use_cache=False)

            assert "unavailable" in str(exc_info.value)

    async def test_handle_cache_error_gracefully(self, mock_redis):
        """Test handling cache errors gracefully."""
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(side_effect=Exception("Redis connection failed"))
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        service = EmbeddingService(redis=mock_redis)

        # Should not raise, just return empty cache
        result = await service._get_cached(["Hello"], "model")
        assert result == {}
