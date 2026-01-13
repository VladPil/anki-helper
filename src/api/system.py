"""Health, metrics, and logs endpoints"""


from fastapi import APIRouter, Depends
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_redis
from src.core.metrics import metrics_endpoint
from src.shared.schemas import HealthResponse

router = APIRouter(prefix="/observability", tags=["Системные"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)  # type: ignore[type-arg]
) -> HealthResponse:
    """Health check endpoint for load balancer."""
    dependencies: dict[str, str] = {}

    try:
        await db.execute(text("SELECT 1"))
        dependencies["postgres"] = "healthy"
    except Exception as e:
        dependencies["postgres"] = f"unhealthy: {e}"

    try:
        await redis.ping()  # type: ignore[misc]
        dependencies["redis"] = "healthy"
    except Exception as e:
        dependencies["redis"] = f"unhealthy: {e}"

    status = "healthy" if all("unhealthy" not in v for v in dependencies.values()) else "unhealthy"

    return HealthResponse(status=status, version="1.0.0", dependencies=dependencies)


@router.get("/ready")
async def readiness_check() -> dict[str, bool]:
    """Readiness check endpoint."""
    return {"ready": True}


@router.get("/live")
async def liveness_check() -> dict[str, bool]:
    """Liveness check endpoint."""
    return {"alive": True}


@router.get("/metrics")
async def get_metrics() -> Response:
    """Prometheus metrics endpoint."""
    return await metrics_endpoint()  # type: ignore[misc]
