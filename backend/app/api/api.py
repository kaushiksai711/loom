from fastapi import APIRouter
from backend.app.api.endpoints import session, harvest, ingest, chat, graph, seeds, crystallize, export

api_router = APIRouter()
api_router.include_router(session.router, prefix="/session", tags=["session"])
api_router.include_router(harvest.router, prefix="/harvest", tags=["harvest"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_router.include_router(chat.router, prefix="/session/chat", tags=["chat"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(seeds.router, prefix="/seeds", tags=["seeds"])
api_router.include_router(crystallize.router, prefix="/session/crystallize", tags=["crystallize"])
api_router.include_router(export.router, prefix="/session/export", tags=["export"])
