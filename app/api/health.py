from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def get_health() -> HealthResponse:
    """Liveness probe for the dashboard."""
    return HealthResponse(status="ok", version="0.1.0")
