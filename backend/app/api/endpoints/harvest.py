from fastapi import APIRouter, HTTPException
from backend.app.models.session import HarvestRequest
from backend.app.workflows.harvest import app as harvest_app
from backend.app.services.graph_rag import GraphRAGService

router = APIRouter()
rag_service = GraphRAGService()

@router.post("/initiate")
async def initiate_harvest(harvest_in: HarvestRequest):
    """
    Starts the Neurosymbolic Harvest Workflow.
    """
    try:
        # 1. Ingest Raw Seed (Vector Store)
        rag_service.ingest_document(
            content=harvest_in.highlight, 
            metadata={
                "source_url": harvest_in.source_url,
                "session_id": harvest_in.session_id,
                "type": "highlight"
            }
        )
        # 2. Skip Workflow for now (Capture Only mode)
        # result = await harvest_app.ainvoke(inputs)
        
        return {
            "status": "buffered", 
            "message": "Seed captured successfully"
        }
        
    except Exception as e:
        import traceback
        error_detail = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        print(error_detail) # Keep server log
        raise HTTPException(status_code=500, detail=error_detail)
