"""FastAPI роутер для RAG эндпоинтов.

Предоставляет REST API для:
    - POST /search - Поиск похожих карточек
    - POST /index - Индексация карточек пользователя
    - POST /reindex - Переиндексация всех карточек пользователя
    - DELETE /index/{card_id} - Удаление карточки из индекса
    - POST /duplicates - Проверка на дубликаты карточек
    - GET /stats/{user_id} - Статистика индексации
    - GET /similar/{card_id} - Поиск похожих карточек
"""

import logging
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.services.rag.schemas import (
    CardStatus,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    DuplicateMatch,
    DuplicateResult,
    IndexRequest,
    IndexResponse,
    IndexStatsResponse,
    ReindexRequest,
    ReindexResponse,
    RemoveFromIndexResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SimilarCardsResponse,
)
from src.services.rag.service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


async def get_redis() -> Redis | None:
    """Получить клиент Redis для кэширования эмбеддингов.

    Returns:
        Redis | None: Клиент Redis или None если недоступен.
    """
    try:
        from redis.asyncio import Redis

        from src.core.config import settings

        redis = Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password or None,
            db=settings.redis.db,
            decode_responses=False,
        )
        # Test connection
        await redis.ping()
        return redis
    except Exception as e:
        logger.warning(f"Redis not available for RAG caching: {e}")
        return None


async def get_rag_service(
    db: AsyncSession = Depends(get_db),
    redis: Redis | None = Depends(get_redis),
) -> RAGService:
    """Получить экземпляр RAGService с зависимостями.

    Args:
        db: Сессия базы данных.
        redis: Опциональный клиент Redis.

    Returns:
        RAGService: Экземпляр сервиса RAG.
    """
    return RAGService(db=db, redis=redis)


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Поиск похожих карточек",
    description="Поиск похожих карточек с использованием векторного сходства.",
)
async def search_cards(
    request: SearchRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> SearchResponse:
    """Поиск похожих карточек с использованием векторного сходства.

    Поддерживает три типа поиска:
    - vector: Чистый векторный поиск по сходству эмбеддингов
    - keyword: Полнотекстовый поиск по ключевым словам
    - hybrid: Комбинация векторного и ключевого поиска с использованием RRF

    Поиск ограничен карточками указанного пользователя и может фильтроваться
    по колоде, статусу и тегам.

    Args:
        request: Параметры поискового запроса.
        rag_service: Экземпляр сервиса RAG.

    Returns:
        SearchResponse: Результаты поиска с метаданными.

    Raises:
        HTTPException: 500 при ошибке поиска.
    """
    start_time = time.perf_counter()

    try:
        results = await rag_service.search(
            query=request.query,
            user_id=request.user_id,
            k=request.k,
            threshold=request.threshold,
            search_type=request.search_type,
            deck_ids=request.deck_ids,
            statuses=request.statuses,
            tags=request.tags,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Convert dict results back to SearchResult models
        search_results = [
            SearchResult(
                card_id=UUID(r["card_id"]),
                deck_id=UUID(r["deck_id"]),
                deck_name=r["deck_name"],
                fields=r["fields"],
                tags=r["tags"],
                status=CardStatus(r["status"]),
                similarity=r["similarity"],
                content_text=r["content_text"],
                created_at=r["created_at"],
            )
            for r in results
        ]

        return SearchResponse(
            results=search_results,
            total=len(search_results),
            query=request.query,
            search_type=request.search_type,
            threshold=request.threshold,
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.post(
    "/index",
    response_model=IndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Индексировать карточки",
    description="Индексирует карточки пользователя для векторного поиска.",
)
async def index_cards(
    request: IndexRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> IndexResponse:
    """Индексировать карточки пользователя.

    Если указаны card_ids, индексируются только эти карточки.
    Если card_ids не указан, индексируются все карточки пользователя.

    Карточки с существующими эмбеддингами пропускаются, если force_reindex не True.

    Args:
        request: Параметры запроса на индексацию.
        rag_service: Экземпляр сервиса RAG.

    Returns:
        IndexResponse: Результат индексации с количеством обработанных карточек.

    Raises:
        HTTPException: 500 при ошибке индексации.
    """
    start_time = time.perf_counter()

    try:
        if request.card_ids:
            # Index specific cards
            indexed_count, skipped_count, failed_ids = await rag_service.indexer.index_cards(
                card_ids=request.card_ids,
                force=request.force_reindex,
            )
        else:
            # Index all user's cards
            indexed_count, skipped_count, failed_ids = await rag_service.indexer.index_user_cards(
                user_id=request.user_id,
                force=request.force_reindex,
            )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return IndexResponse(
            indexed_count=indexed_count,
            skipped_count=skipped_count,
            failed_count=len(failed_ids),
            failed_card_ids=failed_ids,
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Indexing failed: {str(e)}",
        )


@router.post(
    "/reindex",
    response_model=ReindexResponse,
    status_code=status.HTTP_200_OK,
    summary="Переиндексировать карточки",
    description="Полностью переиндексирует все карточки пользователя.",
)
async def reindex_cards(
    request: ReindexRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> ReindexResponse:
    """Переиндексировать все карточки пользователя.

    Эта операция:
    1. Опционально удаляет все существующие эмбеддинги пользователя
       (если delete_existing=True)
    2. Генерирует новые эмбеддинги для всех карточек
    3. Сохраняет новые эмбеддинги в базе данных

    Полезно когда:
    - Изменилась модель эмбеддингов
    - Содержимое карточек значительно изменено
    - Есть проблемы с существующими эмбеддингами

    Args:
        request: Параметры запроса на переиндексацию.
        rag_service: Экземпляр сервиса RAG.

    Returns:
        ReindexResponse: Результат переиндексации со статистикой.

    Raises:
        HTTPException: 500 при ошибке переиндексации.
    """
    start_time = time.perf_counter()

    try:
        result = await rag_service.reindex_user_cards(
            user_id=request.user_id,
            delete_existing=request.delete_existing,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return ReindexResponse(
            deleted_count=result["deleted_count"],
            indexed_count=result["indexed_count"],
            failed_count=result["failed_count"],
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error(f"Reindexing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reindexing failed: {str(e)}",
        )


@router.delete(
    "/index/{card_id}",
    response_model=RemoveFromIndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Удалить карточку из индекса",
    description="Удаляет эмбеддинг карточки из поискового индекса.",
)
async def remove_from_index(
    card_id: Annotated[UUID, Path(description="Уникальный идентификатор карточки")],
    rag_service: RAGService = Depends(get_rag_service),
) -> RemoveFromIndexResponse:
    """Удалить карточку из индекса.

    Удаляет эмбеддинг указанной карточки из базы данных.
    Сама карточка не удаляется, только её векторное представление.

    Вызывается автоматически при удалении карточки, но также может
    использоваться для ручного удаления из поискового индекса.

    Args:
        card_id: Идентификатор карточки для удаления из индекса.
        rag_service: Экземпляр сервиса RAG.

    Returns:
        RemoveFromIndexResponse: Результат операции удаления.

    Raises:
        HTTPException: 500 при ошибке удаления.
    """
    try:
        await rag_service.remove_from_index(card_id)

        return RemoveFromIndexResponse(
            success=True,
            card_id=card_id,
            message=f"Card {card_id} removed from index",
        )

    except Exception as e:
        logger.error(f"Failed to remove card {card_id} from index: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove card from index: {str(e)}",
        )


@router.post(
    "/duplicates",
    response_model=DuplicateCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Проверить на дубликаты",
    description="Проверяет новые карточки на наличие дубликатов среди существующих.",
)
async def check_duplicates(
    request: DuplicateCheckRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> DuplicateCheckResponse:
    """Проверить карточки на дубликаты.

    Проверяет список новых карточек на наличие потенциальных дубликатов
    среди существующих карточек пользователя на основе сходства контента.

    Каждая карточка в запросе должна содержать:
    - temp_id: Временный идентификатор карточки
    - fields: Поля карточки (front, back и т.д.)

    Args:
        request: Параметры запроса на проверку дубликатов.
        rag_service: Экземпляр сервиса RAG.

    Returns:
        DuplicateCheckResponse: Результаты проверки с совпадениями и оценками сходства.

    Raises:
        HTTPException: 500 при ошибке проверки.
    """
    start_time = time.perf_counter()

    try:
        results = await rag_service.find_duplicates(
            user_id=request.user_id,
            cards=request.cards,
            threshold=request.threshold,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Convert to response model
        duplicate_results = []
        for r in results:
            matches = [
                DuplicateMatch(
                    existing_card_id=UUID(m["existing_card_id"])
                    if isinstance(m["existing_card_id"], str)
                    else m["existing_card_id"],
                    existing_card_fields=m["existing_card_fields"],
                    similarity=m["similarity"],
                )
                for m in r.get("matches", [])
            ]

            duplicate_results.append(
                DuplicateResult(
                    temp_id=r["temp_id"],
                    is_duplicate=r["is_duplicate"],
                    matches=matches,
                    highest_similarity=r["highest_similarity"],
                )
            )

        duplicates_found = sum(1 for r in duplicate_results if r.is_duplicate)

        return DuplicateCheckResponse(
            results=duplicate_results,
            duplicates_found=duplicates_found,
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error(f"Duplicate check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Duplicate check failed: {str(e)}",
        )


@router.get(
    "/stats/{user_id}",
    response_model=IndexStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить статистику индексации",
    description="Получает статистику индексации карточек пользователя.",
)
async def get_index_stats(
    user_id: Annotated[UUID, Path(description="Идентификатор пользователя")],
    rag_service: RAGService = Depends(get_rag_service),
) -> IndexStatsResponse:
    """Получить статистику индексации пользователя.

    Возвращает информацию о:
    - Общем количестве карточек
    - Количестве проиндексированных карточек
    - Количестве непроиндексированных карточек
    - Проценте покрытия

    Args:
        user_id: Идентификатор пользователя.
        rag_service: Экземпляр сервиса RAG.

    Returns:
        IndexStatsResponse: Статистика индексации.

    Raises:
        HTTPException: 500 при ошибке получения статистики.
    """
    try:
        stats = await rag_service.get_index_stats(user_id)
        return IndexStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get index stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get index stats: {str(e)}",
        )


@router.get(
    "/similar/{card_id}",
    response_model=SimilarCardsResponse,
    status_code=status.HTTP_200_OK,
    summary="Найти похожие карточки",
    description="Находит карточки, похожие на указанную.",
)
async def find_similar_cards(
    card_id: Annotated[UUID, Path(description="Идентификатор исходной карточки")],
    user_id: Annotated[UUID, Query(description="Идентификатор пользователя")],
    k: Annotated[int, Query(ge=1, le=50, description="Количество результатов")] = 5,
    threshold: Annotated[float, Query(ge=0.0, le=1.0, description="Порог сходства")] = 0.7,
    rag_service: RAGService = Depends(get_rag_service),
) -> SimilarCardsResponse:
    """Найти карточки, похожие на данную.

    Полезно для:
    - Предложения связанных карточек для изучения
    - Поиска потенциально избыточных карточек
    - Построения связей между карточками

    Args:
        card_id: Идентификатор карточки для поиска похожих.
        user_id: Идентификатор пользователя.
        k: Количество похожих карточек для возврата.
        threshold: Минимальный порог сходства.
        rag_service: Экземпляр сервиса RAG.

    Returns:
        SimilarCardsResponse: Список похожих карточек.

    Raises:
        HTTPException: 500 при ошибке поиска.
    """
    try:
        results = await rag_service.find_similar_cards(
            card_id=card_id,
            user_id=user_id,
            k=k,
            threshold=threshold,
        )

        return SimilarCardsResponse(
            card_id=card_id,
            similar_cards=results,
            count=len(results),
        )

    except Exception as e:
        logger.error(f"Failed to find similar cards: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find similar cards: {str(e)}",
        )
