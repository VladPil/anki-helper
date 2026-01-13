"""
Embedding service for generating vector embeddings via SOP_LLM.

All embedding requests are routed through the SOP_LLM service which provides:
    - Unified access to embedding models
    - GPU management and VRAM optimization
    - Request queueing and load balancing

Features:
    - Redis caching for embeddings
    - Batch processing with configurable batch size
    - Async HTTP client for API calls
"""

import hashlib
import json
import logging

from redis.asyncio import Redis

from src.core.config import settings
from src.services.llm import get_llm_client

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Main embedding service using SOP_LLM backend.

    All embedding requests go through SOP_LLM service.

    Features:
        - Redis caching for embeddings
        - Batch processing with configurable batch size
        - Automatic retry through SOP_LLM
    """

    def __init__(
        self,
        redis: Redis | None = None,
        cache_ttl: int = 86400 * 7,  # 7 days default
    ) -> None:
        """
        Initialize embedding service.

        Args:
            redis: Redis client for caching. If None, caching is disabled.
            cache_ttl: Cache TTL in seconds.
        """
        self._redis = redis
        self._cache_ttl = cache_ttl
        self._batch_size = settings.embedding.batch_size

    def _get_cache_key(self, text: str, model: str) -> str:
        """Generate cache key for a text-model combination."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"emb:{model}:{text_hash}"

    async def _get_cached(self, texts: list[str], model: str) -> dict[str, list[float]]:
        """Get cached embeddings for texts."""
        if self._redis is None:
            return {}

        cached: dict[str, list[float]] = {}
        keys = [self._get_cache_key(text, model) for text in texts]

        try:
            # Use pipeline for efficient batch get
            pipe = self._redis.pipeline()
            for key in keys:
                pipe.get(key)
            results = await pipe.execute()

            for text, result in zip(texts, results):
                if result is not None:
                    cached[text] = json.loads(result)

        except Exception as e:
            logger.warning(f"Failed to get cached embeddings: {e}")

        return cached

    async def _set_cached(self, embeddings: dict[str, list[float]], model: str) -> None:
        """Cache embeddings."""
        if self._redis is None:
            return

        try:
            pipe = self._redis.pipeline()
            for text, embedding in embeddings.items():
                key = self._get_cache_key(text, model)
                pipe.setex(key, self._cache_ttl, json.dumps(embedding))
            await pipe.execute()

        except Exception as e:
            logger.warning(f"Failed to cache embeddings: {e}")

    async def embed(
        self,
        texts: list[str],
        use_cache: bool = True,
        model_name: str | None = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for a list of texts via SOP_LLM.

        Args:
            texts: List of texts to embed.
            use_cache: Whether to use Redis cache.
            model_name: Optional embedding model name (overrides config).

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        model = model_name or settings.embedding.model
        llm_client = get_llm_client()

        # Check cache
        cached: dict[str, list[float]] = {}
        if use_cache:
            cached = await self._get_cached(texts, model)

        # Find texts that need embedding
        texts_to_embed = [t for t in texts if t not in cached]

        # Generate embeddings for uncached texts in batches
        new_embeddings: dict[str, list[float]] = {}

        for i in range(0, len(texts_to_embed), self._batch_size):
            batch = texts_to_embed[i : i + self._batch_size]

            try:
                # Use SOP_LLM for embedding generation
                batch_embeddings = await llm_client.generate_embeddings(
                    texts=batch,
                    model_name=model,
                )

                for text, embedding in zip(batch, batch_embeddings):
                    new_embeddings[text] = embedding

            except Exception as e:
                logger.error(f"Failed to generate embeddings via SOP_LLM: {e}")
                raise

        # Cache new embeddings
        if use_cache and new_embeddings:
            await self._set_cached(new_embeddings, model)

        # Combine cached and new embeddings in original order
        all_embeddings = {**cached, **new_embeddings}
        return [all_embeddings[text] for text in texts]

    async def embed_single(
        self,
        text: str,
        use_cache: bool = True,
        model_name: str | None = None,
    ) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed.
            use_cache: Whether to use Redis cache.
            model_name: Optional embedding model name.

        Returns:
            Embedding vector.
        """
        embeddings = await self.embed([text], use_cache=use_cache, model_name=model_name)
        return embeddings[0]

    async def calculate_similarity(
        self,
        text1: str,
        text2: str,
        model_name: str | None = None,
    ) -> float:
        """
        Calculate cosine similarity between two texts via SOP_LLM.

        Args:
            text1: First text.
            text2: Second text.
            model_name: Optional embedding model name.

        Returns:
            Similarity score (0.0 to 1.0).
        """
        llm_client = get_llm_client()
        model = model_name or settings.embedding.model

        return await llm_client.calculate_similarity(
            text1=text1,
            text2=text2,
            model_name=model,
        )

    @property
    def dimension(self) -> int:
        """Get the embedding dimension from config."""
        return settings.embedding.dimensions

    @property
    def model_name(self) -> str:
        """Get the model name from config."""
        return settings.embedding.model

    async def close(self) -> None:
        """Close the embedding service (cleanup)."""
        pass


# Singleton service instance
_embedding_service: EmbeddingService | None = None


def get_embedding_service(redis: Redis | None = None) -> EmbeddingService:
    """Get or create the embedding service singleton.

    Args:
        redis: Optional Redis client for caching.

    Returns:
        EmbeddingService instance.
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(redis=redis)
    return _embedding_service


async def close_embedding_service() -> None:
    """Close the embedding service singleton."""
    global _embedding_service
    if _embedding_service is not None:
        await _embedding_service.close()
        _embedding_service = None
