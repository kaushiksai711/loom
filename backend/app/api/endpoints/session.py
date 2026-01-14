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

# --- Phase 12: Generative Scaffolding ---

@router.get("/concept/{concept_id:path}/scaffold")
async def get_concept_scaffold(concept_id: str):
    """
    Returns 4-format learning scaffold for a concept.
    Lazy generation: First request triggers LLM, subsequent requests are cached.
    """
    try:
        scaffold = await rag_service.generate_scaffold(concept_id)
        return scaffold
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Phase 12: Signal Capture (Layer B4) ---

from backend.app.models.session_signal import SessionSignalCreate
from backend.app.db.arango import db
from datetime import datetime

@router.post("/{session_id}/signal")
async def log_signal(session_id: str, signal: SessionSignalCreate):
    """
    Log a user interaction with a scaffold format.
    Used for learning analytics and adaptive priming.
    """
    try:
        arango_db = db.get_db()
        
        # Ensure collection exists
        if not arango_db.has_collection("SessionSignals"):
            arango_db.create_collection("SessionSignals")
        
        signal_doc = {
            "session_id": session_id,
            "concept_id": signal.concept_id,
            "format_chosen": signal.format_chosen,
            "dwell_time_ms": signal.dwell_time_ms,
            "time_since_last_interaction_ms": signal.time_since_last_interaction_ms,
            "interaction_type": signal.interaction_type,
            "created_at": datetime.utcnow().isoformat()
        }
        
        arango_db.collection("SessionSignals").insert(signal_doc)
        return {"status": "logged", "session_id": session_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/signals")
async def get_signals(session_id: str):
    """
    Retrieve all signals for a session (for debrief/analytics).
    """
    try:
        arango_db = db.get_db()
        
        if not arango_db.has_collection("SessionSignals"):
            return []
        
        aql = "FOR s IN SessionSignals FILTER s.session_id == @id SORT s.created_at ASC RETURN s"
        signals = list(arango_db.aql.execute(aql, bind_vars={"id": session_id}))
        return signals
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/debrief")
async def get_session_debrief(session_id: str):
    """
    Generate session learning debrief with format analytics.
    Shows: concepts explored, format distribution, preferred format, reflection prompt.
    """
    try:
        arango_db = db.get_db()
        
        # Get signals
        if not arango_db.has_collection("SessionSignals"):
            signals = []
        else:
            aql = "FOR s IN SessionSignals FILTER s.session_id == @id RETURN s"
            signals = list(arango_db.aql.execute(aql, bind_vars={"id": session_id}))
        
        # Aggregate stats
        format_counts = {"hands_on": 0, "visual": 0, "socratic": 0, "textual": 0}
        concepts_viewed = set()
        total_dwell = 0
        
        for s in signals:
            fmt = s.get("format_chosen")
            if fmt in format_counts:
                format_counts[fmt] += 1
            concepts_viewed.add(s.get("concept_id"))
            total_dwell += s.get("dwell_time_ms", 0)
        
        # Find dominant format
        dominant = max(format_counts, key=format_counts.get) if signals else "textual"
        total_interactions = sum(format_counts.values())
        
        # Generate reflection prompt based on dominant format
        format_names = {
            "hands_on": "Code examples",
            "visual": "Visual diagrams", 
            "socratic": "Thinking questions",
            "textual": "Text explanations"
        }
        
        reflection_prompt = f"You explored concepts mostly using {format_names[dominant]}. What made that approach work for you?"
        
        # Technique suggestion
        suggestion_map = {
            "hands_on": "Try the 'Think' tab next session to deepen conceptual understanding.",
            "visual": "Try the 'Code' tab to see practical implementations.",
            "socratic": "Try the 'Visual' tab to see relationships between ideas.",
            "textual": "Try the 'Think' tab to test your understanding with questions."
        }
        
        return {
            "session_id": session_id,
            "concepts_explored": len(concepts_viewed),
            "total_interactions": total_interactions,
            "total_time_ms": total_dwell,
            "format_distribution": format_counts,
            "preferred_format": dominant,
            "reflection_prompt": reflection_prompt,
            "technique_suggestion": suggestion_map.get(dominant, "Keep exploring different formats!")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
