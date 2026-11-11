from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import repository, schemas
from app.db import get_session

router = APIRouter()


@router.get("/api/stats", response_model=schemas.StatsResponse, tags=["stats"])
def get_stats(session: Session = Depends(get_session)) -> schemas.StatsResponse:
    return schemas.StatsResponse(**repository.get_stats(session))
