from fastapi import APIRouter
from backend.app.api.endpoints import session, harvest, ingest, chat

api_router = APIRouter()
api_router.include_router(session.router, prefix="/session", tags=["session"])
api_router.include_router(harvest.router, prefix="/harvest", tags=["harvest"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_router.include_router(chat.router, prefix="/session/chat", tags=["chat"])
