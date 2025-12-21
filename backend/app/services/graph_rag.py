from typing import List, Dict
from fastembed import TextEmbedding
from backend.app.db.arango import db

class GraphRAGService:
    def __init__(self):
        # Initialize FastEmbed (Lightweight, High Quality, Local)
        # using 'BAAI/bge-small-en-v1.5' for excellent retrieval performance
        self.embedding_model = TextEmbedding("BAAI/bge-small-en-v1.5")
        self.db = db.get_db()

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for text."""
        # FastEmbed returns a generator, consume it
        return list(self.embedding_model.embed([text]))[0]

    async def hybrid_search(self, query: str, session_id: str = None, top_k: int = 5) -> List[Dict]:
        """
        Performs Real Hybrid RAG:
        1. Contextual Vector Search (Scoped to Session OR Global).
        2. Graph Traversal (1-hop neighbors) to find related concepts.
        """
        query_embedding = list(self.embedding_model.embed([query]))[0].tolist()
        
        # AQL: 
        # 1. Find relevant seeds (Vector Search)
        # 2. Filter by SessionID (Critical for focused chat)
        # 3. Traversal (Find what these seeds are connected to)
        
        aql = """
        LET vector_results = (
            FOR doc IN Seeds
            FILTER doc.embedding != null
            FILTER (@session_id == null OR doc.session_id == @session_id)
            LET score = COSINE_SIMILARITY(doc.embedding, @embedding)
            SORT score DESC
            LIMIT @top_k
            RETURN { doc: doc, score: score, type: 'vector' }
        )
        
        LET graph_results = (
            FOR start_node IN vector_results
            FOR v, e, p IN 1..1 ANY start_node.doc GRAPH 'concept_graph'
            RETURN DISTINCT { doc: v, score: 0.5, type: 'graph_neighbor' }
        )
        
        RETURN APPEND(vector_results, graph_results)
        """
        
        cursor = self.db.aql.execute(
            aql, 
            bind_vars={
                "embedding": query_embedding,
                "top_k": top_k,
                "session_id": session_id 
            }
        )
        
        # Determine strictness: If we have session_id, we usually ONLY want that session's context
        # But for 'serendipity', we might want global. 
        # Current implementation: IF session_id is passed, it FILTERS. 
        
        results = [doc for doc in cursor]
        if results and isinstance(results[0], list):
             results = results[0] # Flatten
             
        return results

    def ingest_document(self, content: str, metadata: Dict):
        """
        Embeds and stores a document (Seed) in ArangoDB.
        """
        embedding = self.embed_query(content)
        
        import datetime
        doc = {
            "highlight": content,
            "embedding": embedding.tolist(),
            "created_at": datetime.datetime.utcnow().isoformat(),
            **metadata
        }
        
        self.db.collection("Seeds").insert(doc)
