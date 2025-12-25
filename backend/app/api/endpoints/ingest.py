from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.app.services.ingestion import IngestionService
import shutil
import os
from uuid import uuid4

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), session_id: str = Form(None)):
    """
    Uploads a file, ingests it, and prepares it for the graph.
    If session_id is provided, links evidence to that session.
    """
    try:
        # Save temp file
        file_id = str(uuid4())
        ext = file.filename.split(".")[-1]
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}.{ext}")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 1. Process File -> Chunks
        documents = await IngestionService.process_file(file_path, file.content_type)
        
        # 2. Ingest into ArangoDB (Embedments + Storage)
        from backend.app.services.graph_rag import GraphRAGService
        rag_service = GraphRAGService()
        
        ingested_count = 0
        for doc in documents:
            await rag_service.ingest_document(
                content=doc.page_content,
                metadata={
                    "source": file.filename,
                    "file_type": ext,
                    "chunk_id": doc.metadata.get("start_index", 0),
                    "type": "document_chunk",
                    "session_id": session_id 
                }
            )
            ingested_count += 1
        
        # Cleanup
        # os.remove(file_path) # Keep for debugging for now
        
        return {
            "status": "success", 
            "chunks_count": ingested_count, 
            "preview": documents[0].page_content[:200] if documents else "No content"
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_ingestion_history():
    """
    Returns the latest 10 ingested files/chunks.
    Querying Seeds collection for unique 'source' metadata.
    """
    try:
        from backend.app.db.arango import db
        database = db.get_db()
        if not database.has_collection("Seeds"):
            return []
            
        aql = """
        FOR doc IN Seeds
            SORT doc.created_at DESC
            COLLECT source = doc.source INTO groups = doc
            LIMIT 5
            RETURN {
                filename: source,
                count: LENGTH(groups),
                latest_chunk: groups[0].created_at
            }
        """
        cursor = database.aql.execute(aql)
        return [doc for doc in cursor]
    except Exception as e:
        print(f"History Access Error: {e}")
        return []
