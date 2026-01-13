"""LangGraph workflow for chat with RAG context.

Использует SOP LLM Executor для генерации ответов с поддержкой
multi-turn conversations и RAG контекста.
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.llm_client import LLMClient, LLMConnectionError, get_llm_client
from src.modules.cards.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class ChatState(TypedDict):
    """State for the chat workflow.

    Attributes:
        message: Current user message.
        history: Conversation history.
        context: Session context data.
        context_query: Optional RAG query.
        retrieved_context: Retrieved RAG context.
        sources: Sources used for context.
        response: Generated response.
        tokens: Token count.
    """

    message: str
    history: list[dict]
    context: dict | None
    context_query: str | None
    retrieved_context: str
    sources: list[dict]
    response: str
    tokens: int


@dataclass
class ChatWorkflow:
    """LangGraph workflow for chat with RAG context.

    This workflow:
    1. Retrieves relevant context using RAG (embeddings from sop_llm)
    2. Generates a response using sop_llm Tasks API
    3. Streams the response back to the client

    Attributes:
        db: Database session for RAG queries.
        llm_client: Client for SOP LLM service.
    """

    db: AsyncSession
    llm_client: LLMClient = field(default_factory=get_llm_client)

    def __post_init__(self) -> None:
        """Initialize the workflow graph."""
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph.

        Returns:
            Configured StateGraph.
        """
        workflow = StateGraph(ChatState)

        # Add nodes
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("generate_response", self._generate_response)

        # Add edges
        workflow.set_entry_point("retrieve_context")
        workflow.add_edge("retrieve_context", "generate_response")
        workflow.add_edge("generate_response", END)

        return workflow.compile()

    async def _retrieve_context(self, state: ChatState) -> dict:
        """Retrieve relevant context using RAG.

        Uses sop_llm embeddings API for semantic search.

        Args:
            state: Current workflow state.

        Returns:
            Updated state with retrieved context.
        """
        context_query = state.get("context_query") or state["message"]
        session_context = state.get("context") or {}

        retrieved_context = ""
        sources: list[dict] = []

        try:
            deck_id = session_context.get("deck_id")
            if deck_id:
                logger.debug("RAG query for deck %s: %s", deck_id, context_query)

                # Create embedding service for RAG retrieval
                embedding_service = EmbeddingService(
                    session=self.db,
                    llm_client=self.llm_client,
                )

                # Search for similar cards using semantic search
                try:
                    deck_uuid = UUID(deck_id) if isinstance(deck_id, str) else deck_id
                except (ValueError, TypeError):
                    deck_uuid = None

                cards_with_scores = await embedding_service.search_similar(
                    query=context_query,
                    deck_id=deck_uuid,
                    limit=5,
                    threshold=0.6,  # Lower threshold for broader context
                )

                if cards_with_scores:
                    # Format cards as context
                    context_parts = []
                    for card, score in cards_with_scores:
                        fields = card.fields or {}
                        front = fields.get("Front", "")
                        back = fields.get("Back", "")

                        if front or back:
                            context_parts.append(
                                f"Карточка (релевантность {score:.2f}):\n"
                                f"Вопрос: {front}\n"
                                f"Ответ: {back}"
                            )

                            sources.append({
                                "id": str(card.id),
                                "front": front[:100],
                                "score": round(score, 3),
                            })

                    retrieved_context = "\n\n".join(context_parts)

                    logger.info(
                        "RAG retrieved %d cards for query",
                        len(cards_with_scores),
                        extra={"deck_id": str(deck_id), "query": context_query[:50]},
                    )

        except LLMConnectionError as e:
            logger.warning("Cannot connect to LLM for embeddings: %s", e)

        except Exception as e:
            logger.warning("Error retrieving RAG context: %s", e)

        return {
            "retrieved_context": retrieved_context,
            "sources": sources,
        }

    async def _generate_response(self, state: ChatState) -> dict:
        """Generate a response using the LLM.

        This is a non-streaming version used internally.
        For streaming, use the stream() method directly.

        Args:
            state: Current workflow state.

        Returns:
            Updated state with generated response.
        """
        # This method is used for non-streaming scenarios
        # The actual streaming is handled in stream()
        return {
            "response": "",
            "tokens": 0,
        }

    def _build_messages(
        self,
        message: str,
        history: list[dict],
        retrieved_context: str,
    ) -> list[dict]:
        """Build the messages list for the LLM.

        Args:
            message: Current user message.
            history: Conversation history.
            retrieved_context: Retrieved RAG context.

        Returns:
            List of messages for the LLM.
        """
        messages = []

        # System message with optional RAG context
        system_content = (
            "Ты - полезный AI-ассистент для изучения с помощью карточек Anki. "
            "Помогай пользователям понимать учебный материал, создавать эффективные карточки "
            "и отвечать на вопросы по темам, которые они изучают. "
            "Отвечай на русском языке."
        )

        if retrieved_context:
            system_content += (
                f"\n\nРелевантный контекст из карточек пользователя:\n{retrieved_context}"
            )

        messages.append(
            {
                "role": "system",
                "content": system_content,
            }
        )

        # Add conversation history
        for msg in history:
            if msg["role"] in ("user", "assistant", "system"):
                messages.append(msg)

        # Add current message
        messages.append(
            {
                "role": "user",
                "content": message,
            }
        )

        return messages

    async def stream(
        self,
        message: str,
        history: list[dict],
        context: dict | None = None,
        context_query: str | None = None,
        sop_conversation_id: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream a response to a message.

        This method:
        1. Retrieves RAG context if available
        2. Streams the LLM response via sop_llm Tasks API
        3. Yields chunks with content and metadata

        Args:
            message: User message content.
            history: Conversation history.
            context: Session context data.
            context_query: Optional RAG query.
            sop_conversation_id: Optional sop_llm conversation ID for context.

        Yields:
            Response chunks with type and content.
        """
        # Retrieve context
        state: ChatState = {
            "message": message,
            "history": history,
            "context": context,
            "context_query": context_query,
            "retrieved_context": "",
            "sources": [],
            "response": "",
            "tokens": 0,
        }

        context_result = await self._retrieve_context(state)
        retrieved_context = context_result.get("retrieved_context", "")
        sources = context_result.get("sources", [])

        # Build messages
        messages = self._build_messages(message, history, retrieved_context)

        # Stream from sop_llm
        total_tokens = 0

        try:
            async for chunk in self.llm_client.stream_task(
                messages=messages,
                conversation_id=sop_conversation_id,
                temperature=settings.sop_llm.default_temperature,
                max_tokens=settings.sop_llm.default_max_tokens,
                save_to_conversation=sop_conversation_id is not None,
            ):
                # Handle different chunk types
                chunk_type = chunk.get("type", "")

                if chunk_type == "error":
                    yield {
                        "type": "content",
                        "content": f"Ошибка: {chunk.get('error', 'Unknown error')}",
                    }
                    break

                if chunk_type == "thinking":
                    # Model is processing the request (polling mode)
                    yield {
                        "type": "thinking",
                        "task_id": chunk.get("task_id"),
                    }
                    continue

                # Handle streaming content (OpenAI format)
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield {
                            "type": "content",
                            "content": content,
                        }

                # Track usage if provided
                usage = chunk.get("usage", {})
                if usage:
                    total_tokens = usage.get("total_tokens", 0)

        except LLMConnectionError as e:
            logger.error("Cannot connect to sop_llm: %s", e)
            yield {
                "type": "content",
                "content": (
                    "Извините, сервис ИИ временно недоступен. "
                    "Пожалуйста, попробуйте позже."
                ),
            }

        except Exception as e:
            logger.exception("Error streaming from LLM")
            yield {
                "type": "content",
                "content": f"Произошла ошибка: {str(e)}",
            }

        # Yield metadata at the end
        yield {
            "type": "metadata",
            "tokens": total_tokens,
            "sources": sources,
        }

    async def run(
        self,
        message: str,
        history: list[dict],
        context: dict | None = None,
        context_query: str | None = None,
        sop_conversation_id: str | None = None,
    ) -> str:
        """Run the workflow and return the complete response.

        This is a non-streaming version that collects all chunks.

        Args:
            message: User message content.
            history: Conversation history.
            context: Session context data.
            context_query: Optional RAG query.
            sop_conversation_id: Optional sop_llm conversation ID.

        Returns:
            Complete response string.
        """
        response_parts = []

        async for chunk in self.stream(
            message, history, context, context_query, sop_conversation_id
        ):
            if chunk.get("type") == "content":
                response_parts.append(chunk.get("content", ""))

        return "".join(response_parts)

    async def create_sop_conversation(
        self,
        system_prompt: str | None = None,
        metadata: dict | None = None,
    ) -> str | None:
        """Create a new conversation in sop_llm.

        Args:
            system_prompt: System prompt for the conversation.
            metadata: Additional metadata.

        Returns:
            conversation_id or None if failed.
        """
        try:
            result = await self.llm_client.create_conversation(
                system_prompt=system_prompt or (
                    "Ты - полезный AI-ассистент для изучения с помощью карточек Anki."
                ),
                model=settings.sop_llm.default_model,
                metadata=metadata,
            )
            return result.get("conversation_id")

        except LLMConnectionError as e:
            logger.warning("Cannot create sop_llm conversation: %s", e)
            return None
