"""FastAPI router for prompts endpoints."""

import logging
import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.modules.prompts.models import PromptCategory
from src.modules.prompts.schemas import (
    PromptCreate,
    PromptListResponse,
    PromptResponse,
    PromptUpdate,
    RenderRequest,
    RenderResponse,
)
from src.modules.prompts.service import (
    PromptNameExistsError,
    PromptNotFoundError,
    PromptRenderError,
    PromptService,
    PromptValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompts", tags=["Шаблоны"])


def get_prompt_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PromptService:
    """Dependency for getting PromptService instance."""
    return PromptService(session)


@router.post(
    "",
    response_model=PromptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new prompt",
    description="Create a new LLM prompt template.",
)
async def create_prompt(
    data: PromptCreate,
    service: Annotated[PromptService, Depends(get_prompt_service)],
    created_by: Annotated[str | None, Query(description="User ID creating the prompt")] = None,
) -> PromptResponse:
    """Create a new prompt.

    Args:
        data: Prompt creation data.
        service: Prompt service instance.
        created_by: Optional user ID for audit.

    Returns:
        Created prompt.

    Raises:
        HTTPException: 409 if prompt name already exists.
        HTTPException: 422 if template validation fails.
    """
    try:
        prompt = await service.create(data, created_by=created_by)
        return PromptResponse.model_validate(prompt)
    except PromptNameExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except PromptValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.errors},
        ) from e


@router.get(
    "",
    response_model=PromptListResponse,
    summary="List prompts",
    description="Get paginated list of LLM prompts.",
)
async def list_prompts(
    service: Annotated[PromptService, Depends(get_prompt_service)],
    category: Annotated[PromptCategory | None, Query(description="Filter by category")] = None,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> PromptListResponse:
    """Get paginated list of prompts.

    Args:
        service: Prompt service instance.
        category: Optional filter by category.
        is_active: Optional filter by active status.
        page: Page number (1-indexed).
        size: Items per page.

    Returns:
        Paginated list of prompts.
    """
    prompts, total = await service.get_list(
        category=category,
        is_active=is_active,
        page=page,
        size=size,
    )

    return PromptListResponse(
        items=[PromptResponse.model_validate(p) for p in prompts],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get(
    "/{prompt_id}",
    response_model=PromptResponse,
    summary="Get a prompt",
    description="Get a prompt by ID.",
)
async def get_prompt(
    prompt_id: UUID,
    service: Annotated[PromptService, Depends(get_prompt_service)],
) -> PromptResponse:
    """Get a prompt by ID.

    Args:
        prompt_id: Prompt UUID.
        service: Prompt service instance.

    Returns:
        The requested prompt.

    Raises:
        HTTPException: 404 if prompt not found.
    """
    try:
        prompt = await service.get_by_id(prompt_id)
        return PromptResponse.model_validate(prompt)
    except PromptNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.patch(
    "/{prompt_id}",
    response_model=PromptResponse,
    summary="Update a prompt",
    description="Update an existing prompt. Optionally create a new version.",
)
async def update_prompt(
    prompt_id: UUID,
    data: PromptUpdate,
    service: Annotated[PromptService, Depends(get_prompt_service)],
    updated_by: Annotated[str | None, Query(description="User ID updating the prompt")] = None,
    create_version: Annotated[
        bool, Query(description="Create new version instead of updating in place")
    ] = False,
) -> PromptResponse:
    """Update a prompt.

    Args:
        prompt_id: Prompt UUID.
        data: Prompt update data.
        service: Prompt service instance.
        updated_by: Optional user ID for audit.
        create_version: If True, creates a new version.

    Returns:
        Updated prompt.

    Raises:
        HTTPException: 404 if prompt not found.
        HTTPException: 409 if new name already exists.
        HTTPException: 422 if template validation fails.
    """
    try:
        prompt = await service.update(
            prompt_id,
            data,
            updated_by=updated_by,
            create_version=create_version,
        )
        return PromptResponse.model_validate(prompt)
    except PromptNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except PromptNameExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except PromptValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.errors},
        ) from e


@router.delete(
    "/{prompt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a prompt",
    description="Delete a prompt by ID.",
)
async def delete_prompt(
    prompt_id: UUID,
    service: Annotated[PromptService, Depends(get_prompt_service)],
) -> None:
    """Delete a prompt.

    Args:
        prompt_id: Prompt UUID.
        service: Prompt service instance.

    Raises:
        HTTPException: 404 if prompt not found.
    """
    try:
        await service.delete(prompt_id)
    except PromptNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/{prompt_id}/render",
    response_model=RenderResponse,
    summary="Render a prompt",
    description="Render a prompt template with the provided variables.",
)
async def render_prompt(
    prompt_id: UUID,
    request: RenderRequest,
    service: Annotated[PromptService, Depends(get_prompt_service)],
) -> RenderResponse:
    """Render a prompt with variables.

    Args:
        prompt_id: Prompt UUID.
        request: Render request with variables.
        service: Prompt service instance.

    Returns:
        Rendered prompt.

    Raises:
        HTTPException: 404 if prompt not found.
        HTTPException: 400 if rendering fails.
    """
    try:
        prompt = await service.get_by_id(prompt_id)
        rendered_system, rendered_user = await service.render(prompt_id, request.variables)

        return RenderResponse(
            system_prompt=rendered_system,
            user_prompt=rendered_user,
            prompt_id=prompt_id,
            prompt_version=prompt.version,
        )
    except PromptNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except PromptRenderError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "details": e.details},
        ) from e


@router.get(
    "/{prompt_id}/versions",
    response_model=list[PromptResponse],
    summary="Get prompt versions",
    description="Get all versions of a prompt.",
)
async def get_prompt_versions(
    prompt_id: UUID,
    service: Annotated[PromptService, Depends(get_prompt_service)],
) -> list[PromptResponse]:
    """Get all versions of a prompt.

    Args:
        prompt_id: Prompt UUID (can be any version).
        service: Prompt service instance.

    Returns:
        List of all prompt versions.

    Raises:
        HTTPException: 404 if prompt not found.
    """
    try:
        versions = await service.get_versions(prompt_id)
        return [PromptResponse.model_validate(v) for v in versions]
    except PromptNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
