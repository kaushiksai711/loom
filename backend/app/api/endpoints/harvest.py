from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.db.arango import db
from datetime import datetime
import uuid

router = APIRouter()

class HarvestRequest(BaseModel):
    highlight: str
    context: str
    source_url: str
    session_id: str

@router.post("/initiate")
async def initiate_harvest(harvest_in: HarvestRequest):
    database = db.get_db()
    seeds_col = database.collection("Seeds")
    
    seed_data = harvest_in.model_dump()
    seed_data["_key"] = str(uuid.uuid4())
    seed_data["created_at"] = datetime.utcnow().isoformat()
    seed_data["status"] = "buffered"
    
    meta = seeds_col.insert(seed_data)
    
    return {"status": "success", "seed_id": meta["_id"]}
