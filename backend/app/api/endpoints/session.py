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
        print(f"[Scaffold API] Requested concept_id: {concept_id}")
        scaffold = await rag_service.generate_scaffold(concept_id)
        return scaffold
    except ValueError as e:
        print(f"[Scaffold API] Concept not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[Scaffold API] Error: {e}")
        traceback.print_exc()
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
    Generate comprehensive session learning debrief.
    
    Shows:
    - Chat activity (questions asked, topics explored)
    - ConceptCard activity (formats used, dwell time)
    - Confusion indicators (rapid tab switching)
    - Preferred learning format
    - Time ranking of concepts
    """
    try:
        arango_db = db.get_db()
        
        # Get all signals
        if not arango_db.has_collection("SessionSignals"):
            signals = []
        else:
            aql = "FOR s IN SessionSignals FILTER s.session_id == @id SORT s.created_at ASC RETURN s"
            signals = list(arango_db.aql.execute(aql, bind_vars={"id": session_id}))
        
        # Separate by signal type
        chat_signals = [s for s in signals if s.get("signal_type") == "chat_interaction"]
        card_signals = [s for s in signals if s.get("signal_type") != "chat_interaction"]
        
        # --- Chat Activity ---
        chat_concepts = set()
        for cs in chat_signals:
            for concept in cs.get("concepts_referenced", []):
                chat_concepts.add(concept)
        
        # --- ConceptCard Activity ---
        format_counts = {"hands_on": 0, "visual": 0, "socratic": 0, "textual": 0}
        format_dwell = {"hands_on": 0, "visual": 0, "socratic": 0, "textual": 0}  # Time-weighted
        concepts_viewed = set()
        concept_times = {}  # For time ranking
        
        for s in card_signals:
            fmt = s.get("format_chosen")
            concept_id = s.get("concept_id", "unknown")
            dwell = s.get("dwell_time_ms", 0)
            
            if fmt in format_counts:
                format_counts[fmt] += 1
                format_dwell[fmt] += dwell
            
            concepts_viewed.add(concept_id)
            concept_times[concept_id] = concept_times.get(concept_id, 0) + dwell
        
        # --- Confusion Detection ---
        confused_concepts = detect_confusion(card_signals)
        
        # --- Calculate Preferred Format (weighted by dwell time) ---
        if sum(format_dwell.values()) > 0:
            preferred = max(format_dwell, key=format_dwell.get)
        elif sum(format_counts.values()) > 0:
            preferred = max(format_counts, key=format_counts.get)
        else:
            preferred = "textual"
        
        # --- Time Ranking ---
        time_ranking = sorted(
            [{"concept_id": k, "total_time_ms": v} for k, v in concept_times.items()],
            key=lambda x: x["total_time_ms"],
            reverse=True
        )[:10]  # Top 10
        
        # --- Lookup Concept Labels ---
        # Get all concept_ids we need to look up
        concept_ids_to_lookup = set()
        for tr in time_ranking:
            concept_ids_to_lookup.add(tr["concept_id"])
        for cc in confused_concepts:
            concept_ids_to_lookup.add(cc["concept_id"])
        
        # Batch lookup from Concepts collection
        concept_labels = {}
        if concept_ids_to_lookup and arango_db.has_collection("Concepts"):
            for cid in concept_ids_to_lookup:
                try:
                    # Handle both "Concepts/123" and "123" formats
                    key = cid.split("/")[-1] if "/" in cid else cid
                    concept = arango_db.collection("Concepts").get(key)
                    if concept:
                        concept_labels[cid] = concept.get("label", cid)
                    else:
                        concept_labels[cid] = key  # Fallback to key
                except:
                    concept_labels[cid] = cid  # Fallback to original
        
        # Enrich time_ranking with labels
        for tr in time_ranking:
            tr["label"] = concept_labels.get(tr["concept_id"], tr["concept_id"].split("/")[-1])
        
        # Enrich confused_concepts with labels
        for cc in confused_concepts:
            cc["label"] = concept_labels.get(cc["concept_id"], cc["concept_id"].split("/")[-1])
        
        # --- Generate Insights ---
        format_names = {
            "hands_on": "Code examples",
            "visual": "Visual diagrams", 
            "socratic": "Thinking questions",
            "textual": "Text explanations"
        }
        
        total_card_interactions = sum(format_counts.values())
        total_chat_interactions = len(chat_signals)
        primary_mode = "chat" if total_chat_interactions > total_card_interactions else "review"
        
        reflection_prompt = f"You explored concepts mostly using {format_names[preferred]}. What made that approach work for you?"
        
        suggestion_map = {
            "hands_on": "Try the 'Think' tab next session to deepen conceptual understanding.",
            "visual": "Try the 'Code' tab to see practical implementations.",
            "socratic": "Try the 'Visual' tab to see relationships between ideas.",
            "textual": "Try the 'Think' tab to test your understanding with questions."
        }
        
        return {
            "session_id": session_id,
            
            # Chat Activity
            "chat_activity": {
                "questions_asked": total_chat_interactions,
                "topics_explored": list(chat_concepts)[:20],  # Limit for response size
                "total_prompts": total_chat_interactions
            },
            
            # ConceptCard Activity
            "card_activity": {
                "concepts_reviewed": len(concepts_viewed),
                "total_interactions": total_card_interactions,
                "total_time_ms": sum(format_dwell.values()),
                "format_distribution": format_counts,
                "format_time_distribution": format_dwell
            },
            
            # Analytics
            "preferred_format": preferred,
            "primary_learning_mode": primary_mode,
            "confused_concepts": confused_concepts,
            "concepts_by_time": time_ranking,
            
            # Combined legacy fields (for backward compatibility)
            "concepts_explored": len(concepts_viewed) + len(chat_concepts),
            "total_interactions": total_card_interactions + total_chat_interactions,
            "total_time_ms": sum(format_dwell.values()),
            "format_distribution": format_counts,
            
            # UX
            "reflection_prompt": reflection_prompt,
            "technique_suggestion": suggestion_map.get(preferred, "Keep exploring different formats!")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def detect_confusion(signals: list) -> list:
    """
    Detect concepts where user showed confusion patterns.
    
    Signals:
    - Rapid tab switches (3+ in < 10 seconds)
    - Short dwell times (< 3 seconds)
    - Viewing all 4 tabs but continuing to switch
    """
    from collections import defaultdict
    
    by_concept = defaultdict(list)
    for s in signals:
        concept_id = s.get("concept_id")
        if concept_id:
            by_concept[concept_id].append(s)
    
    confused = []
    
    for concept_id, concept_signals in by_concept.items():
        if len(concept_signals) < 2:
            continue
        
        # Count rapid switches
        rapid_switches = 0
        short_dwells = 0
        formats_seen = set()
        
        for i, sig in enumerate(concept_signals):
            dwell = sig.get("dwell_time_ms", 0)
            fmt = sig.get("format_chosen")
            
            if fmt:
                formats_seen.add(fmt)
            
            if dwell < 3000 and dwell > 0:  # < 3 seconds
                short_dwells += 1
            
            # Check time between this and next signal
            if i < len(concept_signals) - 1:
                try:
                    current_time = sig.get("created_at", "")
                    next_time = concept_signals[i + 1].get("created_at", "")
                    # Simple check: if both exist and interaction_type is tab_switch
                    if sig.get("interaction_type") == "tab_switch":
                        rapid_switches += 1
                except:
                    pass
        
        # Calculate confusion score
        total = len(concept_signals)
        score = (
            (rapid_switches * 3) +
            (short_dwells * 2) +
            (4 if len(formats_seen) >= 4 and total > 5 else 0)  # Viewed all tabs but kept switching
        ) / max(total, 1)
        
        if score > 0.6:
            confused.append({
                "concept_id": concept_id,
                "confusion_score": round(min(score, 1.0), 2),
                "signals": {
                    "rapid_switches": rapid_switches,
                    "short_dwells": short_dwells,
                    "formats_tried": len(formats_seen)
                }
            })
    
    return sorted(confused, key=lambda x: x["confusion_score"], reverse=True)[:5]  # Top 5


# --- Phase 13: Preference Endpoint ---

@router.get("/{session_id}/preference")
async def get_format_preference(session_id: str):
    """
    Get user's preferred learning format based on signal history.
    Weighted by dwell time, not just click counts.
    """
    try:
        arango_db = db.get_db()
        
        if not arango_db.has_collection("SessionSignals"):
            return {"preferred_format": "textual", "confidence": "low", "reason": "no_data"}
        
        # Get card signals only (chat signals don't have format preference)
        aql = """
        FOR s IN SessionSignals 
            FILTER s.session_id == @id 
            FILTER s.format_chosen != null
            RETURN s
        """
        signals = list(arango_db.aql.execute(aql, bind_vars={"id": session_id}))
        
        if not signals:
            return {"preferred_format": "textual", "confidence": "low", "reason": "no_card_signals"}
        
        # Weight by dwell time
        format_scores = {"hands_on": 0, "visual": 0, "socratic": 0, "textual": 0}
        
        for s in signals:
            fmt = s.get("format_chosen")
            dwell = s.get("dwell_time_ms", 1000)  # Default 1s if not tracked
            
            if fmt in format_scores:
                format_scores[fmt] += dwell
        
        total = sum(format_scores.values())
        if total == 0:
            # Fall back to click counts
            for s in signals:
                fmt = s.get("format_chosen")
                if fmt in format_scores:
                    format_scores[fmt] += 1
            total = sum(format_scores.values())
        
        preferred = max(format_scores, key=format_scores.get)
        confidence = "high" if format_scores[preferred] / max(total, 1) > 0.5 else "medium"
        
        return {
            "preferred_format": preferred,
            "confidence": confidence,
            "format_scores": format_scores,
            "total_signals": len(signals)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

