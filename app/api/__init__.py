from fastapi import APIRouter

from app.api import health, jobs, refresh, sources, stats

api_router = APIRouter()


api_router.include_router(health.router)
api_router.include_router(jobs.router)
api_router.include_router(stats.router)
api_router.include_router(sources.router)
api_router.include_router(refresh.router)
