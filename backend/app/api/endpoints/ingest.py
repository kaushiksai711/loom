from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.app.services.ingestion import IngestionService
import shutil
import os
from uuid import uuid4

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Uploads a file, ingests it, and prepares it for the graph.
    """
    try:
        # Save temp file
        file_id = str(uuid4())
        ext = file.filename.split(".")[-1]
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}.{ext}")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Ingest
        documents = await IngestionService.process_file(file_path, file.content_type)
        
        # Cleanup
        # os.remove(file_path) # Keep for debugging for now
        
        return {
            "status": "success", 
            "chunks_count": len(documents), 
            "preview": documents[0].page_content[:200] if documents else "No content"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
