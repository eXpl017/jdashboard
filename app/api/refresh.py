from fastapi import APIRouter, Depends, HTTPException, Request

from app import schemas
from app.services.refresh import (
    RefreshAlreadyRunning,
    RefreshService,
    build_default_refresh_service,
)

router = APIRouter()


def get_refresh_service(request: Request) -> RefreshService:
    """Return the app's refresh service, creating the default one on first use."""
    service = getattr(request.app.state, "refresh_service", None)
    if service is None:
        service = build_default_refresh_service()
        request.app.state.refresh_service = service
    return service


@router.post(
    "/api/refresh",
    status_code=202,
    response_model=schemas.RefreshStartResponse,
    tags=["refresh"],
)
async def start_refresh(
    payload: schemas.RefreshRequest | None = None,
    service: RefreshService = Depends(get_refresh_service),
) -> schemas.RefreshStartResponse:
    """Start a manual refresh. Only one refresh may run at a time."""
    try:
        progress = await service.start(
            window_days=payload.window_days if payload else None
        )
    except RefreshAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return schemas.RefreshStartResponse(run_id=progress.run_id, status="running")


@router.get(
    "/api/refresh/status",
    response_model=schemas.RefreshStatusResponse,
    tags=["refresh"],
)
async def refresh_status(
    service: RefreshService = Depends(get_refresh_service),
) -> schemas.RefreshStatusResponse:
    """Return in-memory progress for the current or most recent run."""
    progress = service.snapshot()
    if progress is None:
        return schemas.RefreshStatusResponse()
    return schemas.RefreshStatusResponse(
        run_id=progress.run_id,
        status=progress.status,
        started_at=progress.started_at,
        finished_at=progress.finished_at,
        current_source=progress.current_source,
        sources=progress.sources,
    )
