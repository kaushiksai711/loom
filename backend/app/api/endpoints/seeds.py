from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.services.graph_rag import GraphRAGService

router = APIRouter()
rag_service = GraphRAGService()

class UserSeedRequest(BaseModel):
    text: str
    comment: str = ""
    confidence: str = "High"

@router.post("")
async def create_user_seed(seed: UserSeedRequest):
    """
    Creates a new User Seed (Wisdom) in the Knowledge Graph.
    """
    try:
        await rag_service.add_user_seed(
            text=seed.text,
            comment=seed.comment,
            confidence=seed.confidence
        )
        return {"status": "success", "message": "Wisdom crystallized into the graph."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
