from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks
from backend.app.services.ingestion import IngestionService
import shutil
import os
from uuid import uuid4

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), session_id: str = Form(None)):
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
        full_text_buffer = []

        for doc in documents:
            # Aggregate text for batch extraction
            full_text_buffer.append(doc.page_content)

            # Ingest Seed (Vector) - Disable per-chunk extraction!
            await rag_service.ingest_document(
                content=doc.page_content,
                metadata={
                    **doc.metadata, # Preserve original metadata (e.g. page, source)
                    "source": file.filename,
                    "file_type": ext,
                    "chunk_id": doc.metadata.get("start_index", 0),
                    "type": "document_chunk",
                    "session_id": session_id 
                },
                extract_concepts=False # <--- CRITICAL: Don't extract per chunk (Wasteful)
            )
            ingested_count += 1
        
        # 3. Trigger Batch Extraction (Async Background)
        if full_text_buffer:
            full_text = "\n".join(full_text_buffer)
            # Add to background tasks -> Returns immediately
            print(f"--- Queuing Background Extraction for {file.filename} ---")
            background_tasks.add_task(
                rag_service.process_batch_extraction,
                full_text=full_text,
                source_name=file.filename,
                session_id=session_id
            )
        
        # Cleanup (Optional: Keep for debugging if needed, or remove later)
        # os.remove(file_path) 
        
        return {
            "status": "success", 
            "chunks_count": ingested_count,
            "message": "File uploaded. Extraction processing in background.",
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
