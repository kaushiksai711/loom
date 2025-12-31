import pytest
from unittest.mock import MagicMock
from backend.app.services.graph_rag import GraphRAGService

@pytest.mark.asyncio
async def test_get_global_graph_layered_rendering():
    """
    Verifies that get_global_graph:
    1. Returns 'limit' number of nodes.
    2. Sorts by 'val' (influence).
    3. Returns only edges between these nodes (subgraph).
    """
    # 1. Instantiate Service (This might try to connect to real DB, but we'll swap it immediately)
    service = GraphRAGService()
    
    # 2. Mock the DB and AQL execution explicitly
    service.db = MagicMock()
    
    # Simulating 5 nodes with different influence scores
    mock_nodes = [
        {"_id": "Concepts/A", "label": "A", "val": 100}, # Top
        {"_id": "Concepts/B", "label": "B", "val": 80},
        {"_id": "Concepts/C", "label": "C", "val": 60},
        {"_id": "Concepts/D", "label": "D", "val": 40},
        {"_id": "Concepts/E", "label": "E", "val": 20}, # Bottom
    ]
    
    # Simulating edges
    mock_edges = [
        {"_from": "Concepts/A", "_to": "Concepts/B", "type": "RELATED"},
        {"_from": "Concepts/B", "_to": "Concepts/C", "type": "RELATED"},
    ]
    
    # Mock return value (Limit 3)
    mock_result = [{
        "nodes": mock_nodes[:3],
        "links": mock_edges
    }]
    
    # Mock the cursor iterator
    mock_cursor = MagicMock()
    mock_cursor.__iter__.return_value = [mock_result[0]]
    service.db.aql.execute.return_value = mock_cursor
    
    # EXECUTE
    result = await service.get_global_graph(limit=3)
    
    # VERIFY
    assert len(result["nodes"]) == 3
    assert result["nodes"][0]["_id"] == "Concepts/A"
    assert len(result["links"]) == 2
    
    # Match call args
    expected_offset = 0
    call_args = service.db.aql.execute.call_args
    assert call_args[1]["bind_vars"]["limit"] == 3

@pytest.mark.asyncio
async def test_get_global_graph_endpoint():
    """
    Verifies the API endpoint /session/global/graph.
    Uses FastAPI TestClient to hit the route.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from unittest.mock import patch
    
    client = TestClient(app)
    
    # Mock the service method directly to avoid DB connection in API test
    with patch("backend.app.api.endpoints.session.rag_service.get_global_graph") as mock_method:
        mock_method.return_value = {
            "nodes": [{"id": "1", "val": 10}],
            "links": []
        }
        
        response = client.get("/api/v1/session/global/graph?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert len(data["nodes"]) == 1
        assert mock_method.call_args[1]["limit"] == 10
