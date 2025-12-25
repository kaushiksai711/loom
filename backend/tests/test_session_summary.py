import pytest
from backend.app.services.graph_rag import GraphRAGService
from backend.app.db.arango import db
import datetime

@pytest.mark.asyncio
async def test_session_summary_flow():
    rag_service = GraphRAGService()
    
    # 1. Create Session
    session_id = await rag_service.create_session("Test Summary Session", "Testing Summary")
    assert session_id is not None
    
    # 2. Add Dummy Data (Direct DB Insert for speed/control)
    database = db.get_db()
    
    # Seed (Evidence)
    seed_doc = {
        "highlight": "Original Evidence Text",
        "embedding": [0.1] * 384, # Mock embedding
        "created_at": datetime.datetime.utcnow().isoformat(),
        "session_id": session_id,
        "type": "seed"
    }
    seed_meta = database.collection("Seeds").insert(seed_doc)
    seed_id = seed_meta["_id"]
    
    # UserSeed (Thought)
    user_seed_doc = {
        "text": "Original Thought Text",
        "embedding": [0.2] * 384,
        "created_at": (datetime.datetime.utcnow() + datetime.timedelta(seconds=1)).isoformat(),
        "session_id": session_id,
        "type": "user_seed",
        "confidence": "High"
    }
    user_seed_meta = database.collection("UserSeeds").insert(user_seed_doc)
    user_seed_id = user_seed_meta["_id"]
    
    # 3. Test GET Summary
    summary = await rag_service.get_session_summary(session_id)
    assert summary["title"] == "Test Summary Session"
    assert len(summary["timeline"]) == 2
    assert summary["timeline"][0]["type"] == "evidence"
    assert summary["timeline"][1]["type"] == "thought"
    
    # 4. Test PATCH Content
    # Update Evidence
    await rag_service.update_session_content(session_id, seed_id, "Updated Evidence Text")
    
    # Update Thought
    await rag_service.update_session_content(session_id, user_seed_id, "Updated Thought Text")
    
    # Verify Updates
    updated_summary = await rag_service.get_session_summary(session_id)
    assert updated_summary["timeline"][0]["content"].startswith("Updated Evidence Text")
    assert updated_summary["timeline"][1]["content"] == "Updated Thought Text"
