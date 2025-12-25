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

class UpdateContentRequest(BaseModel):
    item_id: str
    content: str

@router.get("/{session_id}/summary")
async def get_session_summary_endpoint(session_id: str):
    """
    Returns the full session report including temporal log.
    """
    summary = await rag_service.get_session_summary(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")
    return summary

@router.patch("/{session_id}/content")
async def update_session_content_endpoint(session_id: str, request: UpdateContentRequest):
    """
    Updates the content of a specific item (Seed/UserSeed) in the session.
    """
    try:
        updated = await rag_service.update_session_content(session_id, request.item_id, request.content)
        return {"status": "success", "updated": updated}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
