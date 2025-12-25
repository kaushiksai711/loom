from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any
from backend.app.services.graph_rag import GraphRAGService

router = APIRouter()
rag_service = GraphRAGService()

class CommitRequest(BaseModel):
    approved_merges: List[Dict[str, Any]]
    new_nodes: List[Dict[str, Any]]

@router.post("/{session_id}/preview")
async def preview_crystallization(session_id: str):
    """
    Generates a merge proposal for the session.
    """
    try:
        proposal = await rag_service.preview_crystallization(session_id)
        return proposal
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/commit")
async def commit_crystallization(session_id: str, request: CommitRequest):
    """
    Executes the crystallization commit.
    """
    try:
        result = await rag_service.commit_crystallization(
            session_id, 
            request.approved_merges, 
            request.new_nodes
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
