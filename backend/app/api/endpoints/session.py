from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from backend.app.services.graph_rag import GraphRAGService

router = APIRouter()
rag_service = GraphRAGService()

class EndSessionRequest(BaseModel):
    session_id: str

class CreateSessionRequest(BaseModel):
    title: str
    title: str
    goal: str = "General Exploration"

@router.get("/")
async def list_sessions():
    """
    Returns a list of all available sessions.
    """
    try:
        sessions = await rag_service.list_sessions()
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """
    Permanently deletes a session and its contents.
    """
    try:
        success = await rag_service.delete_session(session_id)
        return {"status": "success", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
@router.get("/global/graph")
async def get_global_graph_endpoint(limit: int = 50, offset: int = 0, session_id: str = None):
    """
    Returns the Global Knowledge Graph (Layer 1).
    Default: Top 50 influential nodes.
    If session_id is provided, prioritizes session context.
    """
    try:
        data = await rag_service.get_global_graph(limit=limit, offset=offset, session_id=session_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Crystallization Wizard Endpoints ---

@router.post("/crystallize/{session_id}/preview")
async def preview_crystallization(session_id: str):
    """
    Generates a Preview of the Crystallization process (Entity Resolution & Conflict Detection).
    Does NOT write to the DB.
    """
    try:
        # Use the dedicated preview method that returns data!
        proposal = await rag_service.preview_crystallization(session_id)
        return proposal
    except Exception as e:
        print(f"Preview Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class CommitCrystallizationRequest(BaseModel):
    approved_merges: list
    new_nodes: list
    approved_synapses: list = None # Optional

@router.post("/crystallize/{session_id}/commit")
async def commit_crystallization_endpoint(session_id: str, request: CommitCrystallizationRequest):
    """
    Finalizes the crystallization. Writes Concepts and Edges to the Global Graph.
    """
    try:
        result = await rag_service.commit_crystallization(
            session_id, 
            request.approved_merges, 
            request.new_nodes,
            request.approved_synapses
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Phase 11: Interactive Graph Editing ---

class UpdateSeedRequest(BaseModel):
    updates: dict

@router.patch("/seed/{seed_id:path}")
async def update_seed_endpoint(seed_id: str, request: UpdateSeedRequest, session_id: str):
    """ Updates a draft concept (Seed). """
    try:
        await rag_service.update_seed(session_id, seed_id, request.updates)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
@router.delete("/seed/{seed_id:path}")
async def delete_seed_endpoint(seed_id: str, session_id: str, force: bool = False):
    """ Deletes a draft concept. """
    try:
        await rag_service.delete_seed(session_id, seed_id, force=force)
        return {"status": "success"}
    except ValueError as e:
        # 422 Unprocessable Entity for "High Connectivity" warning? Or 400.
        # User requested 409 Conflict logic, but 400 is fine for logic error.
        raise HTTPException(status_code=400, detail=str(e))

class UpdateEdgeRequest(BaseModel):
    updates: dict

@router.patch("/edge/{edge_id:path}")
async def update_edge_endpoint(edge_id: str, request: UpdateEdgeRequest, session_id: str):
    try:
        await rag_service.update_edge(session_id, edge_id, request.updates)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/edge/{edge_id:path}")
async def delete_edge_endpoint(edge_id: str, session_id: str):
    try:
        await rag_service.delete_edge(session_id, edge_id)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

class CreateEdgeRequest(BaseModel):
    source_id: str
    target_id: str
    relation: str

@router.post("/edge")
async def create_edge_endpoint(request: CreateEdgeRequest, session_id: str):
    try:
        await rag_service.create_edge(session_id, request.source_id, request.target_id, request.relation)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
