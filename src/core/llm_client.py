"""Клиент для SOP LLM сервиса.

Обеспечивает интеграцию с SOP LLM Executor для:
- Создания задач генерации (tasks)
- Управления диалогами (conversations)
- Генерации эмбеддингов (embeddings)
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Базовая ошибка клиента LLM."""

    pass


class LLMConnectionError(LLMClientError):
    """Ошибка подключения к LLM сервису."""

    pass


class LLMTaskError(LLMClientError):
    """Ошибка выполнения задачи LLM."""

    pass


@dataclass
class LLMClient:
    """Асинхронный клиент для SOP LLM Executor.

    Использует Tasks API для асинхронной генерации и Conversations API
    для multi-turn диалогов.

    Attributes:
        base_url: URL сервиса sop_llm.
        timeout: Таймаут запросов в секундах.
        default_model: Модель по умолчанию.
    """

    base_url: str = field(default_factory=lambda: settings.sop_llm.api_base_url)
    timeout: int = field(default_factory=lambda: settings.sop_llm.timeout)
    default_model: str = field(default_factory=lambda: settings.sop_llm.default_model)

    def _get_client(self) -> httpx.AsyncClient:
        """Создать HTTP клиент."""
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout, connect=10),
        )

    # =========================================================================
    # Conversations API
    # =========================================================================

    async def create_conversation(
        self,
        system_prompt: str | None = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Создать новый диалог.

        Args:
            system_prompt: Системный промпт для диалога.
            model: Модель по умолчанию для диалога.
            metadata: Дополнительные метаданные.

        Returns:
            Данные созданного диалога с conversation_id.

        Raises:
            LLMConnectionError: При ошибке подключения.
        """
        payload: dict[str, Any] = {}
        if system_prompt:
            payload["system_prompt"] = system_prompt
        if model:
            payload["model"] = model
        if metadata:
            payload["metadata"] = metadata

        try:
            async with self._get_client() as client:
                response = await client.post("/api/v1/conversations/", json=payload)
                response.raise_for_status()
                return response.json()

        except httpx.ConnectError as e:
            logger.error("Cannot connect to sop_llm: %s", e)
            raise LLMConnectionError(
                f"Cannot connect to LLM service at {self.base_url}"
            ) from e

        except httpx.HTTPStatusError as e:
            logger.error("sop_llm error: %s", e.response.text)
            raise LLMClientError(f"LLM service error: {e.response.status_code}") from e

    async def get_conversation(
        self, conversation_id: str, include_messages: bool = True
    ) -> dict[str, Any] | None:
        """Получить диалог по ID.

        Args:
            conversation_id: ID диалога (формат conv_xxx).
            include_messages: Включить историю сообщений.

        Returns:
            Данные диалога или None если не найден.
        """
        try:
            async with self._get_client() as client:
                response = await client.get(
                    f"/api/v1/conversations/{conversation_id}",
                    params={"include_messages": include_messages},
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()

        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Cannot connect to LLM service at {self.base_url}"
            ) from e

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Удалить диалог.

        Args:
            conversation_id: ID диалога.

        Returns:
            True если удалён успешно.
        """
        try:
            async with self._get_client() as client:
                response = await client.delete(
                    f"/api/v1/conversations/{conversation_id}"
                )
                return response.status_code == 204

        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Cannot connect to LLM service at {self.base_url}"
            ) from e

    async def add_message(
        self, conversation_id: str, role: str, content: str
    ) -> dict[str, Any]:
        """Добавить сообщение в диалог.

        Args:
            conversation_id: ID диалога.
            role: Роль (user, assistant, system).
            content: Текст сообщения.

        Returns:
            Добавленное сообщение.
        """
        try:
            async with self._get_client() as client:
                response = await client.post(
                    f"/api/v1/conversations/{conversation_id}/messages",
                    json={"role": role, "content": content},
                )
                response.raise_for_status()
                return response.json()

        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Cannot connect to LLM service at {self.base_url}"
            ) from e

    # =========================================================================
    # Tasks API
    # =========================================================================

    async def create_task(
        self,
        prompt: str | None = None,
        messages: list[dict[str, str]] | None = None,
        model: str | None = None,
        conversation_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        save_to_conversation: bool = True,
        **extra_params: Any,
    ) -> dict[str, Any]:
        """Создать задачу генерации.

        Args:
            prompt: Текст промпта.
            messages: Явная история сообщений.
            model: Модель для генерации.
            conversation_id: ID диалога для контекста.
            temperature: Температура генерации.
            max_tokens: Максимум токенов.
            stream: Включить стриминг.
            save_to_conversation: Сохранять в историю диалога.
            **extra_params: Дополнительные параметры.

        Returns:
            Данные созданной задачи с task_id.
        """
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "stream": stream,
            "save_to_conversation": save_to_conversation,
        }

        if prompt:
            payload["prompt"] = prompt
        if messages:
            payload["messages"] = messages
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        payload.update(extra_params)

        try:
            async with self._get_client() as client:
                response = await client.post("/api/v1/tasks/", json=payload)
                response.raise_for_status()
                return response.json()

        except httpx.ConnectError as e:
            logger.error("Cannot connect to sop_llm: %s", e)
            raise LLMConnectionError(
                f"Cannot connect to LLM service at {self.base_url}"
            ) from e

        except httpx.HTTPStatusError as e:
            logger.error("sop_llm task error: %s", e.response.text)
            raise LLMTaskError(f"Task creation failed: {e.response.text}") from e

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Получить статус задачи.

        Args:
            task_id: ID задачи.

        Returns:
            Данные задачи или None если не найдена.
        """
        try:
            async with self._get_client() as client:
                response = await client.get(f"/api/v1/tasks/{task_id}")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()

        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Cannot connect to LLM service at {self.base_url}"
            ) from e

    async def wait_for_task(
        self, task_id: str, poll_interval: float = 0.5, max_wait: float = 120.0
    ) -> dict[str, Any]:
        """Ждать завершения задачи.

        Args:
            task_id: ID задачи.
            poll_interval: Интервал polling в секундах.
            max_wait: Максимальное время ожидания.

        Returns:
            Данные завершённой задачи.

        Raises:
            LLMTaskError: Если задача не завершилась вовремя или с ошибкой.
        """
        import asyncio

        elapsed = 0.0
        while elapsed < max_wait:
            task = await self.get_task(task_id)
            if task is None:
                raise LLMTaskError(f"Task {task_id} not found")

            status = task.get("status")
            if status == "completed":
                return task
            if status == "failed":
                error = task.get("error", "Unknown error")
                raise LLMTaskError(f"Task failed: {error}")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise LLMTaskError(f"Task {task_id} timed out after {max_wait}s")

    async def stream_task(
        self,
        prompt: str | None = None,
        messages: list[dict[str, str]] | None = None,
        model: str | None = None,
        conversation_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        save_to_conversation: bool = True,
        poll_interval: float = 2.0,
        max_wait: float = 300.0,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Создать задачу и получить ответ через polling.

        sop_llm использует асинхронную модель с очередями.
        Этот метод создаёт задачу и периодически проверяет её статус,
        возвращая результат когда задача завершена.

        Args:
            prompt: Текст промпта.
            messages: Явная история сообщений.
            model: Модель для генерации.
            conversation_id: ID диалога для контекста.
            temperature: Температура генерации.
            max_tokens: Максимум токенов.
            save_to_conversation: Сохранять в историю диалога.
            poll_interval: Интервал проверки статуса (секунды).
            max_wait: Максимальное время ожидания (секунды).

        Yields:
            Чанки ответа: сначала {"type": "thinking"}, затем результат.
        """
        try:
            # Создаём задачу
            task_result = await self.create_task(
                prompt=prompt,
                messages=messages,
                model=model,
                conversation_id=conversation_id,
                temperature=temperature,
                max_tokens=max_tokens,
                save_to_conversation=save_to_conversation,
            )
            task_id = task_result.get("task_id")

            if not task_id:
                yield {
                    "type": "error",
                    "error": "Failed to create task: no task_id returned",
                }
                return

            # Сообщаем что задача создана и модель "думает"
            yield {
                "type": "thinking",
                "task_id": task_id,
            }

            # Polling: проверяем статус каждые poll_interval секунд
            import asyncio

            elapsed = 0.0
            while elapsed < max_wait:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                task_status = await self.get_task(task_id)
                if not task_status:
                    yield {
                        "type": "error",
                        "error": f"Task {task_id} not found",
                    }
                    return

                status = task_status.get("status")

                if status == "completed":
                    # Задача завершена успешно
                    result = task_status.get("result", {})
                    content = result.get("text", "") if isinstance(result, dict) else str(result)

                    # Возвращаем результат в формате OpenAI-like для совместимости
                    yield {
                        "choices": [{"delta": {"content": content}}],
                    }

                    # Возвращаем usage если есть
                    usage = result.get("usage", {}) if isinstance(result, dict) else {}
                    if usage:
                        yield {"usage": usage}

                    return

                elif status == "failed":
                    error = task_status.get("error", "Unknown error")
                    yield {
                        "type": "error",
                        "error": error,
                    }
                    return

                # status == "pending" или "processing" - продолжаем ждать

            # Timeout
            yield {
                "type": "error",
                "error": f"Task {task_id} timed out after {max_wait}s",
            }

        except LLMConnectionError as e:
            logger.error("Cannot connect to sop_llm: %s", e)
            yield {
                "type": "error",
                "error": str(e),
            }

        except LLMTaskError as e:
            logger.error("sop_llm task error: %s", e)
            yield {
                "type": "error",
                "error": str(e),
            }

    # =========================================================================
    # Embeddings API
    # =========================================================================

    async def generate_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Сгенерировать эмбеддинги для текстов.

        Args:
            texts: Список текстов.
            model: Модель эмбеддингов.

        Returns:
            Список векторов (embeddings).

        Raises:
            LLMClientError: При ошибке генерации.
        """
        if not texts:
            return []

        model = model or settings.embedding.model

        try:
            async with self._get_client() as client:
                response = await client.post(
                    "/api/v1/embeddings/",
                    json={"texts": texts, "model_name": model},
                )
                response.raise_for_status()
                result = response.json()
                return result.get("embeddings", [])

        except httpx.ConnectError as e:
            logger.error("Cannot connect to sop_llm for embeddings: %s", e)
            raise LLMConnectionError(
                f"Cannot connect to LLM service at {self.base_url}"
            ) from e

        except httpx.HTTPStatusError as e:
            logger.error("sop_llm embeddings error: %s", e.response.text)
            raise LLMClientError(f"Embeddings error: {e.response.text}") from e

    async def calculate_similarity(
        self,
        text1: str,
        text2: str,
        model: str | None = None,
    ) -> float:
        """Вычислить сходство двух текстов.

        Args:
            text1: Первый текст.
            text2: Второй текст.
            model: Модель эмбеддингов.

        Returns:
            Косинусное сходство (0.0 - 1.0).
        """
        model = model or settings.embedding.model

        try:
            async with self._get_client() as client:
                response = await client.post(
                    "/api/v1/embeddings/similarity",
                    json={
                        "text1": text1,
                        "text2": text2,
                        "model_name": model,
                    },
                )
                response.raise_for_status()
                result = response.json()
                return result.get("similarity", 0.0)

        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Cannot connect to LLM service at {self.base_url}"
            ) from e

    # =========================================================================
    # Health Check
    # =========================================================================

    async def is_available(self) -> bool:
        """Проверить доступность сервиса.

        Returns:
            True если сервис доступен.
        """
        try:
            async with self._get_client() as client:
                response = await client.get("/health")
                return response.status_code == 200
        except Exception:
            return False


# Синглтон клиента
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Получить singleton LLM клиента."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
