"""
RAG (Retrieval-Augmented Generation) module for AnkiRAG.

This module provides vector similarity search capabilities for flashcards using pgvector.

Components:
    - RAGService: Main service orchestrating indexing and retrieval
    - CardIndexer: Indexes cards into pgvector
    - CardRetriever: Searches for similar cards
    - EmbeddingService: Generates embeddings via multiple providers
"""

from src.services.rag.embeddings import EmbeddingService
from src.services.rag.indexer import CardIndexer
from src.services.rag.retriever import CardRetriever
from src.services.rag.service import RAGService

__all__ = [
    "RAGService",
    "CardIndexer",
    "CardRetriever",
    "EmbeddingService",
]
