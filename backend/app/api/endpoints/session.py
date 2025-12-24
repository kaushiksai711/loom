from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from backend.app.services.graph_rag import GraphRAGService

router = APIRouter()
rag_service = GraphRAGService()

class EndSessionRequest(BaseModel):
    session_id: str

class CreateSessionRequest(BaseModel):
    title: str
    goal: str = "General Exploration"

@router.post("/create")
async def create_new_session(request: CreateSessionRequest):
    """
    Starts a new learning session.
    Returns a UUID to be used for Sync.
    """
    try:
        session_id = await rag_service.create_session(request.title, request.goal)
        return {
            "session_id": session_id, 
            "status": "active",
            "message": "Session Initialized. Sync this ID with your extension."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/end")
async def end_session(request: EndSessionRequest, background_tasks: BackgroundTasks):
    """
    Triggers Asynchronous Consolidation.
    1. Entity Linking (Conservative)
    2. Mastery Update (Structural)
    3. Archiving
    """
    try:
        # Run in background to stay responsive
        background_tasks.add_task(rag_service.consolidate_session, request.session_id)
        return {"status": "consolidation_started", "message": "Brain structure updating in background."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
