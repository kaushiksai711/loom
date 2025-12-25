import pytest
from backend.app.services.graph_rag import GraphRAGService
from backend.app.db.arango import db
import datetime

@pytest.mark.asyncio
async def test_crystallization_flow():
    rag_service = GraphRAGService()
    database = db.get_db()
    
    # Clean DB
    for col in ["Concepts", "UserSeeds", "Relationships", "Sessions", "Seeds"]:
        if database.has_collection(col):
            database.collection(col).truncate()

    # 1. Setup Session & Data
    session_id = await rag_service.create_session("Crystallize Test", "Testing Merge")
    
    # Existing Concept "AI"
    ai_vector = [1.0 if i % 2 == 0 else 0.0 for i in range(384)] # [1, 0, 1, 0...]
    ai_doc = {
        "label": "Artificial Intelligence",
        "definition": "Simulated intelligence",
        "embedding": ai_vector,
        "type": "concept",
        "status": "crystallized"
    }
    ai_meta = database.collection("Concepts").insert(ai_doc)
    ai_id = ai_meta["_id"]
    
    # UserSeed: "AI is cool" (Matches AI)
    # Same direction as AI vector
    seed_merge = {
        "text": "AI systems",
        "comment": "AI is cool",
        "embedding": ai_vector, 
        "created_at": datetime.datetime.utcnow().isoformat(),
        "type": "user_seed",
        "session_id": session_id
    }
    database.collection("UserSeeds").insert(seed_merge)
    
    # UserSeed: "Unique Thought" (Should be New Node)
    # Orthogonal direction: [0, 1, 0, 1...]
    xenoblade_vector = [0.0 if i % 2 == 0 else 1.0 for i in range(384)]
    seed_new = {
        "text": "Xenoblade Chronicles",
        "comment": "Best game",
        "embedding": xenoblade_vector, # Similarity should be 0.0 with AI
        "created_at": datetime.datetime.utcnow().isoformat(),
        "type": "user_seed",
        "session_id": session_id
    }
    database.collection("UserSeeds").insert(seed_new)

    # 2. Test Preview
    proposal = await rag_service.preview_crystallization(session_id)
    
    print("\n--- Proposal ---")
    print(proposal)
    
    # Expect 1 Merge (AI) and 1 New Node (Xenoblade)
    has_merge = False
    for m in proposal["proposed_merges"]:
        if m["target_id"] == ai_id:
            has_merge = True
            assert m["confidence"] > 0.9 # Should be high
            
    # Note: New Nodes might be empty in the proposal dict list itself if logic separates them, 
    # but my logic put them in 'new_nodes_count' or handled implicitly.
    # Looking at my code: `new_nodes` list exists but is not returned in MVP dict except count.
    # Wait, I should verify the return dict structure in `preview_crystallization`.
    # It returns { ..., "proposed_merges": [], "new_nodes_count": int, ... }
    
    assert has_merge, "Should propose merging 'AI systems' with 'Artificial Intelligence'"
    # assert proposal["new_nodes_count"] >= 1 # Xenoblade

    # 3. Test Commit
    # Construct commit payload matching the proposal
    approved_merges = proposal["proposed_merges"]
    
    # Use the returned new_nodes directly
    new_nodes_payload = proposal["new_nodes"]
    assert len(new_nodes_payload) >= 1
    
    res = await rag_service.commit_crystallization(session_id, approved_merges, new_nodes_payload)
    assert res["status"] == "success"
    
    # 4. Verify DB State
    # Check "Xenoblade" is now a Concept
    xenoblade = list(database.aql.execute("FOR c IN Concepts FILTER c.label == 'Xenoblade Chronicles' RETURN c"))
    assert len(xenoblade) == 1
    assert xenoblade[0]["status"] == "crystallized"
    
    # Check Session is Archived
    sess = list(database.aql.execute("FOR s IN Sessions FILTER s._key == @k RETURN s", bind_vars={"k": session_id}))[0]
    assert sess["status"] == "crystallized"

