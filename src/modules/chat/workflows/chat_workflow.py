"""LangGraph workflow for chat with RAG context."""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings

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
    1. Retrieves relevant context using RAG
    2. Generates a response using the LLM
    3. Streams the response back to the client

    Attributes:
        db: Database session for RAG queries.
        llm_base_url: Base URL for the LLM service.
        llm_api_key: API key for the LLM service.
    """

    db: AsyncSession
    llm_base_url: str = field(default_factory=lambda: settings.sop_llm.api_base_url)
    llm_api_key: str = field(default_factory=lambda: "")  # Not used by sop_llm
    llm_timeout: int = field(default_factory=lambda: settings.sop_llm.timeout)

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

        Args:
            state: Current workflow state.

        Returns:
            Updated state with retrieved context.
        """
        context_query = state.get("context_query") or state["message"]
        session_context = state.get("context") or {}

        # TODO: Implement actual RAG retrieval
        # This is a placeholder that should be connected to the vector store
        retrieved_context = ""
        sources: list[dict] = []

        try:
            # Placeholder for RAG retrieval
            # In production, this would:
            # 1. Embed the context_query
            # 2. Query the vector store
            # 3. Retrieve relevant documents
            # 4. Format them as context

            deck_id = session_context.get("deck_id")
            if deck_id:
                logger.debug("RAG query for deck %s: %s", deck_id, context_query)
                # Placeholder: retrieve from vector store
                # retrieved_docs = await self._vector_store.similarity_search(
                #     query=context_query,
                #     filter={"deck_id": str(deck_id)},
                #     k=5,
                # )
                # retrieved_context = "\n\n".join(
                #     doc.page_content for doc in retrieved_docs
                # )
                # sources = [
                #     {"id": doc.metadata.get("id"), "title": doc.metadata.get("title")}
                #     for doc in retrieved_docs
                # ]

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
            "You are a helpful AI assistant for Anki flashcard learning. "
            "Help users understand their study material, create effective flashcards, "
            "and answer questions about topics they're learning."
        )

        if retrieved_context:
            system_content += (
                f"\n\nRelevant context from the user's flashcards:\n{retrieved_context}"
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
    ) -> AsyncGenerator[dict, None]:
        """Stream a response to a message.

        This method:
        1. Retrieves RAG context if available
        2. Streams the LLM response
        3. Yields chunks with content and metadata

        Args:
            message: User message content.
            history: Conversation history.
            context: Session context data.
            context_query: Optional RAG query.

        Yields:
            Response chunks with type and content.
        """
        import httpx

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

        # Stream from LLM
        total_tokens = 0

        try:
            async with httpx.AsyncClient(timeout=self.llm_timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.llm_base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.llm_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messages": messages,
                        "stream": True,
                        "temperature": 0.7,
                        "max_tokens": 2048,
                    },
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue

                        data = line[6:]  # Remove "data: " prefix

                        if data == "[DONE]":
                            break

                        try:
                            import json

                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                yield {
                                    "type": "content",
                                    "content": content,
                                }

                            # Track tokens if provided
                            usage = chunk.get("usage", {})
                            if usage:
                                total_tokens = usage.get("total_tokens", 0)

                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

        except httpx.HTTPStatusError as e:
            logger.error("LLM HTTP error: %s", e)
            yield {
                "type": "content",
                "content": (
                    "I apologize, but I encountered an error generating a response. "
                    "Please try again."
                ),
            }

        except httpx.TimeoutException:
            logger.error("LLM request timeout")
            yield {
                "type": "content",
                "content": "The request timed out. Please try again with a shorter message.",
            }

        except Exception as e:
            logger.exception("Error streaming from LLM")
            yield {
                "type": "content",
                "content": f"An error occurred: {str(e)}",
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
    ) -> str:
        """Run the workflow and return the complete response.

        This is a non-streaming version that collects all chunks.

        Args:
            message: User message content.
            history: Conversation history.
            context: Session context data.
            context_query: Optional RAG query.

        Returns:
            Complete response string.
        """
        response_parts = []

        async for chunk in self.stream(message, history, context, context_query):
            if chunk.get("type") == "content":
                response_parts.append(chunk.get("content", ""))

        return "".join(response_parts)
