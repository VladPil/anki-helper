"""Base workflow class with LangGraph best practices."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import StateGraph
from opentelemetry import trace
from pydantic import BaseModel

from src.core.logging import get_structured_logger

logger = get_structured_logger(__name__)
tracer = trace.get_tracer(__name__)


class WorkflowState(TypedDict, total=False):
    """Base state for all workflows.

    Using TypedDict for LangGraph state management.
    All workflows should extend this with their specific fields.
    """

    # Common fields
    trace_id: str
    job_id: str
    step: str
    error: str | None

    # Progress tracking
    progress: float
    total_steps: int
    current_step_index: int

    # Cancellation
    is_cancelled: bool


class WorkflowResult(BaseModel):
    """Result of a workflow execution."""

    success: bool
    data: dict[str, Any]
    error: str | None = None
    trace_id: str | None = None


class BaseWorkflow(ABC):
    """Base class for LangGraph workflows.

    Provides common functionality for workflow implementation
    following LangGraph best practices:

    1. State Management: Use TypedDict for state
    2. Node Functions: Pure functions that take state and return updates
    3. Conditional Edges: Use for routing logic
    4. Error Handling: Graceful error handling with state updates
    5. Observability: Tracing and logging at each step
    """

    def __init__(self, name: str | None = None) -> None:
        """Initialize the workflow.

        Args:
            name: Optional workflow name for logging/tracing.
        """
        self.name = name or self.__class__.__name__
        self._graph: StateGraph | None = None
        self._compiled = None

    @property
    def graph(self) -> StateGraph:
        """Get or create the workflow graph.

        Returns:
            Configured StateGraph instance.
        """
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    @property
    def compiled(self):
        """Get the compiled workflow.

        Returns:
            Compiled LangGraph workflow.
        """
        if self._compiled is None:
            self._compiled = self.graph.compile()
        return self._compiled

    @abstractmethod
    def _build_graph(self) -> StateGraph:
        """Build the workflow graph.

        Subclasses must implement this to define their workflow.

        Returns:
            Configured StateGraph.
        """
        pass

    async def run(
        self,
        trace_id: str | None = None,
        on_progress: Callable[[str], Any] | None = None,
        is_cancelled: Callable[[], Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run the workflow.

        Args:
            trace_id: Optional trace ID for distributed tracing.
            on_progress: Optional callback for progress updates.
            is_cancelled: Optional callback to check cancellation.
            **kwargs: Workflow-specific input parameters.

        Returns:
            Workflow result dictionary.
        """
        import uuid

        if trace_id is None:
            trace_id = str(uuid.uuid4())

        with tracer.start_as_current_span(
            f"workflow.{self.name}",
            attributes={"workflow.name": self.name, "trace.id": trace_id},
        ) as span:
            logger.info(
                f"Starting workflow: {self.name}",
                trace_id=trace_id,
                inputs=list(kwargs.keys()),
            )

            try:
                # Build initial state
                initial_state = self._build_initial_state(
                    trace_id=trace_id,
                    **kwargs,
                )

                # Inject callbacks into state if needed
                if on_progress is not None:
                    initial_state["_on_progress"] = on_progress
                if is_cancelled is not None:
                    initial_state["_is_cancelled"] = is_cancelled

                # Run the compiled graph
                result = await self.compiled.ainvoke(initial_state)

                # Extract final state
                final_state = dict(result)

                # Clean up internal callbacks
                final_state.pop("_on_progress", None)
                final_state.pop("_is_cancelled", None)

                if final_state.get("error"):
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", final_state["error"])
                    logger.error(
                        f"Workflow {self.name} completed with error",
                        trace_id=trace_id,
                        error=final_state["error"],
                    )
                else:
                    logger.info(
                        f"Workflow {self.name} completed successfully",
                        trace_id=trace_id,
                    )

                return final_state

            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                span.record_exception(e)

                logger.error(
                    f"Workflow {self.name} failed",
                    trace_id=trace_id,
                    error=str(e),
                    exc_info=True,
                )

                return {
                    "error": str(e),
                    "trace_id": trace_id,
                }

    async def run_stream(
        self,
        trace_id: str | None = None,
        **kwargs: Any,
    ):
        """Run the workflow with streaming.

        Yields state updates as the workflow progresses.

        Args:
            trace_id: Optional trace ID for distributed tracing.
            **kwargs: Workflow-specific input parameters.

        Yields:
            State update dictionaries.
        """
        import uuid

        if trace_id is None:
            trace_id = str(uuid.uuid4())

        with tracer.start_as_current_span(
            f"workflow.{self.name}.stream",
            attributes={"workflow.name": self.name, "trace.id": trace_id},
        ):
            logger.info(
                f"Starting streaming workflow: {self.name}",
                trace_id=trace_id,
            )

            try:
                # Build initial state
                initial_state = self._build_initial_state(
                    trace_id=trace_id,
                    **kwargs,
                )

                # Stream through the compiled graph
                async for state_update in self.compiled.astream(initial_state):
                    # Yield progress events for each node
                    for node_name, node_state in state_update.items():
                        yield {
                            "type": "progress",
                            "step": node_name,
                            "state": node_state,
                        }

                        # If this node produced cards, yield them
                        if isinstance(node_state, dict):
                            cards = node_state.get("cards", [])
                            for card in cards:
                                if isinstance(card, dict) and "front" in card:
                                    yield {
                                        "type": "card",
                                        "card": card,
                                        "progress": node_state.get("progress", 0),
                                    }

            except Exception as e:
                logger.error(
                    f"Streaming workflow {self.name} failed",
                    trace_id=trace_id,
                    error=str(e),
                )
                yield {
                    "type": "error",
                    "error": str(e),
                }

    def _build_initial_state(
        self,
        trace_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build the initial state for the workflow.

        Args:
            trace_id: Trace ID for the workflow.
            **kwargs: Additional state fields.

        Returns:
            Initial state dictionary.
        """
        return {
            "trace_id": trace_id,
            "step": "init",
            "error": None,
            "progress": 0.0,
            "is_cancelled": False,
            **kwargs,
        }

    @staticmethod
    def create_node(
        name: str,
        description: str | None = None,
    ):
        """Decorator for creating traced workflow nodes.

        Args:
            name: Node name for logging/tracing.
            description: Optional description.

        Returns:
            Decorated function.
        """

        def decorator(func: Callable):
            async def wrapper(state: dict[str, Any]) -> dict[str, Any]:
                with tracer.start_as_current_span(
                    f"node.{name}",
                    attributes={
                        "node.name": name,
                        "node.description": description or "",
                    },
                ):
                    logger.debug(f"Executing node: {name}")

                    # Check for cancellation
                    is_cancelled = state.get("_is_cancelled")
                    if is_cancelled and callable(is_cancelled):
                        import asyncio

                        if asyncio.iscoroutinefunction(is_cancelled):
                            cancelled = await is_cancelled()
                        else:
                            cancelled = is_cancelled()

                        if cancelled:
                            logger.info(f"Node {name} cancelled")
                            return {"is_cancelled": True, "step": name}

                    # Execute the node
                    try:
                        result = await func(state)

                        # Update progress callback if available
                        on_progress = state.get("_on_progress")
                        if on_progress and callable(on_progress):
                            import asyncio

                            if asyncio.iscoroutinefunction(on_progress):
                                await on_progress(name)
                            else:
                                on_progress(name)

                        return {**result, "step": name}

                    except Exception as e:
                        logger.error(f"Node {name} failed", error=str(e))
                        return {"error": str(e), "step": name}

            wrapper.__name__ = func.__name__
            return wrapper

        return decorator

    @staticmethod
    def should_continue(state: dict[str, Any]) -> bool:
        """Check if workflow should continue.

        Args:
            state: Current workflow state.

        Returns:
            True if workflow should continue.
        """
        if state.get("is_cancelled"):
            return False
        if state.get("error"):
            return False
        return True
