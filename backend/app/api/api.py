from fastapi import APIRouter
from backend.app.api.endpoints import session, harvest

api_router = APIRouter()
api_router.include_router(session.router, prefix="/session", tags=["session"])
api_router.include_router(harvest.router, prefix="/harvest", tags=["harvest"])
