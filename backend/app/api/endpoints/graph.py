from fastapi import APIRouter, HTTPException
from backend.app.db.arango import db

router = APIRouter()

@router.get("", response_model=dict)
async def get_graph_data():
    """
    Fetch all crystallized concepts and relationships for visualization.
    """
    database = db.get_db()
    
    # Check if collections exist
    if not database.has_collection("Concepts") or not database.has_collection("Relationships"):
        return {"nodes": [], "links": []}

    # Fetch Nodes (Concepts)
    # Return format compatible with react-force-graph: { id, name, val, group }
    # Fetch Nodes (Concepts + Seeds)
    # Return format compatible with react-force-graph: { id, name, val, group }
    aql_nodes = """
    LET concepts = (
        FOR doc IN Concepts
        RETURN {
            id: doc._id,
            name: doc.label,
            val: doc.type == 'source' ? 10 : (doc.importance || 5),
            group: doc.type == 'source' ? 'source' : 'concept'
        }
    )
    
    LET seeds = (
        FOR doc IN Seeds
        SORT doc.created_at DESC
        LIMIT 50
        RETURN {
            id: doc._id,
            name: LEFT(doc.highlight, 20) || '...',
            val: 2,
            group: 'seed'
        }
    )
    
    RETURN APPEND(concepts, seeds)
    """
    cursor_nodes = database.aql.execute(aql_nodes)
    # The query returns a single list because of APPEND, so we take the first element (which is the list)
    # Wait, APPEND returns [ [ ... ] ]? AQL APPEND returns a single array. 
    # db.aql.execute returns a cursor. If the query returns a single list, cursor.next() gets it.
    # However, standard AQL `RETURN [1,2]` returns 1 doc which is `[1,2]`.
    # Let's adjust python side to handle this safely.
    
    result_list = list(cursor_nodes)
    nodes = result_list[0] if result_list else []

    # Fetch Edges (Relationships)
    # Return format: { source, target, type }
    aql_edges = """
    FOR doc IN Relationships
        RETURN {
            source: doc._from,
            target: doc._to,
            type: doc.type
        }
    """
    cursor_edges = database.aql.execute(aql_edges)
    cursor_edges = database.aql.execute(aql_edges)
    raw_links = [doc for doc in cursor_edges]
    
    # Filter links: ensure source and target are in nodes
    node_ids = set(n['id'] for n in nodes)
    links = [
        l for l in raw_links 
        if l['source'] in node_ids and l['target'] in node_ids
    ]

    return {"nodes": nodes, "links": links}

@router.get("/node")
async def get_node_details_endpoint(id: str):
    """
    Fetches rich details for a specific node ID (Concept or Source).
    ID should be the full ArangoID (e.g., 'Concepts/Cognitive_Loom').
    """
    from backend.app.services.graph_rag import GraphRAGService
    service = GraphRAGService()
    
    try:
        details = await service.get_node_details(id)
        if not details:
            raise HTTPException(status_code=404, detail="Node not found")
        return details
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
