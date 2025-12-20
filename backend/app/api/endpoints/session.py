from fastapi import APIRouter, HTTPException
from backend.app.models.session import Session, SessionCreate
from backend.app.db.arango import db
from datetime import datetime
import uuid

router = APIRouter()

@router.post("/create", response_model=Session)
async def create_session(session_in: SessionCreate):
    database = db.get_db()
    sessions_col = database.collection("Sessions")
    
    session_data = session_in.model_dump(by_alias=True)
    # _key is required by ArangoDB, but we can let Arango generate it or generate it ourselves.
    # Our model expects _key and _id, which usually come from DB.
    # For creation, we generate a key.
    key = str(uuid.uuid4())
    session_data["_key"] = key
    session_data["created_at"] = datetime.utcnow().isoformat()
    
    # Insert
    meta = sessions_col.insert(session_data)
    
    # Update data with DB metadata for response
    session_data["_id"] = meta["_id"]
    session_data["_key"] = meta["_key"]
    
    return session_data

@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: str):
    database = db.get_db()
    sessions_col = database.collection("Sessions")
    
    # ArangoDB _id is Collection/Key. If session_id is just Key, we might need to handle that.
    # Assuming session_id passed here is the Key.
    if "/" not in session_id:
        # It's a key, construct ID or use get
        if not sessions_col.has(session_id):
             raise HTTPException(status_code=404, detail="Session not found")
        session = sessions_col.get(session_id)
    else:
        # It's a full ID
        try:
            session = database.document(session_id)
        except Exception:
             raise HTTPException(status_code=404, detail="Session not found")
            
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return session
