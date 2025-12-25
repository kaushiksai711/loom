import pytest
from backend.app.services.graph_rag import GraphRAGService
from backend.app.db.arango import db
import datetime

@pytest.mark.asyncio
async def test_export_flow():
    rag_service = GraphRAGService()
    database = db.get_db()
    
    # Clean DB
    for col in ["Sessions", "UserSeeds", "Concepts"]:
        if database.has_collection(col):
            database.collection(col).truncate()

    # 1. Setup Session & Data
    session_id = await rag_service.create_session("Export Test", "Testing Exports")
    
    # Add Evidence (Seeds)
    database.collection("Seeds").insert({
        "highlight": "Hello Export",
        "source": "Test Source",
        "created_at": datetime.datetime.utcnow().isoformat(),
        "session_id": session_id
    })
    
    # Add Thought (UserSeeds)
    database.collection("UserSeeds").insert({
        "text": "My thought",
        "created_at": datetime.datetime.utcnow().isoformat(),
        "type": "user_seed",
        "session_id": session_id
    })
    
    # 2. Test Markdown Export
    md = await rag_service.generate_markdown_export(session_id)
    print("\n--- Markdown Export ---\n", md)
    assert "# Export Test" in md
    assert "**Goal**: Testing Exports" in md
    assert "Hello Export" in md
    assert "### 📄" in md
    
    # 3. Test Mermaid Export
    mermaid = await rag_service.generate_mermaid_diagram(session_id)
    print("\n--- Mermaid Export ---\n", mermaid)
    # Since we didn't add graph data (Concepts/Links) explicitly in get_session_summary for UserSeeds without connections,
    # Mermaid might be empty or just definitions.
    # GraphRAGService.get_session_summary aggregates UserSeeds.
    # But generate_mermaid_diagram relies on 'graph_data'.
    # get_session_summary logic for graph_data:
    # It builds concept_map if UserSeeds match concepts.
    # In this test, we have no connections.
    # So graph_data might be empty.
    
    # Let's Assert base structure at least
    assert "graph TD" in mermaid
    assert "classDef evidence" in mermaid

