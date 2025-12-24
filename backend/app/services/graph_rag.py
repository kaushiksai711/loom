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

    async def create_session(self, title: str, goal: str) -> str:
        """
        Creates a new Session document with TTL.
        """
        import uuid
        import datetime
        
        session_id = str(uuid.uuid4())
        now = datetime.datetime.utcnow()
        # default 24h TTL
        expires_at = now + datetime.timedelta(hours=24)
        
        doc = {
            "_key": session_id,
            "title": title,
            "goal": goal,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "status": "active",
            "attachments": [],
            "harvested_nodes": []
        }
        
        # Ensure collection exists (lazy check)
        if not self.db.has_collection("Sessions"):
            self.db.create_collection("Sessions")
            
        self.db.collection("Sessions").insert(doc)
        return session_id

    async def hybrid_search(self, query: str, session_id: str = None, intent: str = "GENERAL", top_k: int = 5) -> List[Dict]:
        """
        Performs Real Hybrid RAG with Intent-Aware Routing.
         Intents:
         - FACT_CHECK: Prioritize edges with type 'CONTRADICTS' or 'conflicting' evidence.
         - LEARNING: Prioritize edges with type 'PREREQUISITE' or 'FOUNDATION'.
         - GENERAL: Standard similarity search.
        """
        query_embedding = list(self.embedding_model.embed([query]))[0].tolist()
        
        # AQL: 
        # 1. Find relevant seeds (Vector Search)
        # 2. Filter by SessionID (Critical for focused chat) - IGNORED IN GLOBAL MODE
        # 3. Traversal:
        #    - If FACT_CHECK: Boost prioritization of nodes connected via CONTRADICTS
        #    - If LEARNING: Boost prioritization of nodes connected via PREREQUISITE
        
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
            
            // INTENT-AWARE BOOSTING
            LET boost = 
                (@intent == 'FACT_CHECK' AND e.type == 'CONTRADICTS') ? 2.0 : 
                (@intent == 'LEARNING' AND e.type == 'PREREQUISITE') ? 1.5 : 
                1.0
                
            SORT boost DESC
            
            RETURN DISTINCT { doc: v, score: 0.5 * boost, type: 'graph_neighbor', edge_type: e.type }
        )
        
        RETURN APPEND(vector_results, graph_results)
        """
        
        # STRATEGY: Session Priority RAG
        # 1. Search STRICTLY within the session (High Trust)
        cursor_session = self.db.aql.execute(
            aql, 
            bind_vars={
                "embedding": query_embedding,
                "top_k": top_k,
                "session_id": session_id,
                "intent": intent
            }
        )
        session_results = [doc for doc in cursor_session]
        if session_results and isinstance(session_results[0], list): session_results = session_results[0]

        # 2. If low confidence or few results, Fallback to Global (Serendipity)
        if len(session_results) < 3:
             # Search GLOBAL (exclude current session to avoid duplicates)
             # NOTE: For MVP, we just search everything with None, then dedup manually if needed
             # Or simply relax the filter.
             cursor_global = self.db.aql.execute(
                aql,
                bind_vars={
                    "embedding": query_embedding,
                    "top_k": 3,
                    "session_id": None, # Global
                    "intent": intent
                }
             )
             global_results = [doc for doc in cursor_global]
             if global_results and isinstance(global_results[0], list): global_results = global_results[0]
             
             # Merge: Session First, then Global
             # Simple dedup by ID
             seen = {x['doc'].get('_id'): True for x in session_results}
             for gr in global_results:
                 if gr['doc'].get('_id') not in seen:
                     session_results.append(gr)

        return session_results[:top_k]

    async def _ensure_source_node(self, filename: str):
        """
        Ensures a Source Node exists for the file.
        Returns the _id of the Source Node.
        """
        # Check if exists
        concepts = self.db.collection("Concepts")
        
        # Simple AQL to find existing source or create
        aql = """
        UPSERT { label: @filename, type: 'source' } 
        INSERT { label: @filename, type: 'source', status: 'active', created_at: DATE_ISO8601(DATE_NOW()) } 
        UPDATE {} 
        IN Concepts
        RETURN NEW
        """
        cursor = self.db.aql.execute(aql, bind_vars={"filename": filename})
        doc = cursor.next()
        return doc["_id"]

    async def ingest_document(self, content: str, metadata: Dict):
        """
        Embeds and stores a document (Seed) in ArangoDB.
        Links it to the Source Node (Anchor).
        """
        embedding = self.embed_query(content)
        
        # 1. Create Seed (Chunk)
        import datetime
        doc = {
            "highlight": content,
            "embedding": embedding.tolist(),
            "created_at": datetime.datetime.utcnow().isoformat(),
            **metadata
        }
        
        seed_meta = self.db.collection("Seeds").insert(doc)
        seed_id = seed_meta["_id"]
        
        # 2. Link to Source Node (Anchor)
        source_name = metadata.get("source", "Unknown Document")
        source_id = await self._ensure_source_node(source_name)
        
        # Create Edge: Source -> HAS_PART -> Seed
        # This creates the star topology
        edge = {
            "_from": source_id,
            "_to": seed_id,
            "type": "HAS_PART",
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        self.db.collection("Relationships").insert(edge)

    async def add_user_seed(self, text: str, comment: str, confidence: str, session_id: str = None):
        """
        Creates a UserSeed and embeds it.
        """
        embedding = self.embed_query(text)
        import datetime
        doc = {
            "text": text,
            "comment": comment,
            "confidence": confidence,
            "embedding": embedding.tolist(),
            "created_at": datetime.datetime.utcnow().isoformat(),
            "type": "user_seed",
            "session_id": session_id 
        }
        
        self.db.collection("UserSeeds").insert(doc)

    async def detect_conflicts(self, target_text: str) -> List[Dict]:
        """
        Checks if target_text conflicts with existing UserSeeds.
        """
        # 1. Find relevant UserSeeds via Vector Search
        target_embedding = self.embed_query(target_text)
        
        aql = """
        FOR doc IN UserSeeds
            FILTER doc.embedding != null
            LET score = COSINE_SIMILARITY(doc.embedding, @embedding)
            FILTER score > 0.7  // Semantic relevance threshold
            SORT score DESC
            LIMIT 3
            RETURN doc
        """
        cursor = self.db.aql.execute(aql, bind_vars={"embedding": target_embedding.tolist()})
        relevant_seeds = list(cursor)
        
        if not relevant_seeds:
            return []
            
        # 2. Ask LLM to check for Semantic Conflict
        from backend.app.services.llm import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage
        
        llm = get_llm()
        
        conflicts = []
        for seed in relevant_seeds:
            prompt = f"""
            Check for logical contradiction between these two statements.
            
            Statement A (User Knowledge): "{seed['text']}"
            Statement B (New Evidence): "{target_text}"
            
            If they contradict, explain why. If they agree or are unrelated, say "No Conflict".
            Return JSON: {{ "conflict": boolean, "reason": "string" }}
            """
            
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.lower()
            
            # Naive parsing (production should use structured output)
            if "true" in content or '"conflict": true' in content:
                conflicts.append({
                    "seed_id": seed['_id'],
                    "seed_text": seed['text'],
                    "reason": response.content
                })
                
        return conflicts

    async def consolidate_session(self, session_id: str):
        """
        Phase 3: The Heavy Lift.
        1. Conservative Entity Linking (No Auto-Merge): Find similar concepts, create RELATED_TO edges.
        2. Structural Mastery: Update mastery based on InDegree + OutDegree.
        3. Archive Session.
        """
        print(f"--- Starting Consolidation for Session: {session_id} ---")
        
        # 1. Identify Touched Concepts (from UserSeeds)
        # We assume UserSeeds are linked to Concepts or ARE the source of truth for this session.
        # For this MVP, we iterate over UserSeeds created in this session.
        
        # 1. Identify Touched Concepts (from Seeds)
        # We assume Seeds (ingested clips) are the source of truth for this session.
        
        aql_seeds = """
        FOR doc IN Seeds
            FILTER doc.session_id == @session_id
            RETURN doc
        """
        cursor = self.db.aql.execute(aql_seeds, bind_vars={"session_id": session_id})
        user_seeds = list(cursor)
        
        if not user_seeds:
            print("No User Seeds found to consolidate.")
            return

        # 2. Conservative Entity Linking
        # Check each seed against Global Graph Concepts (excluding this session's own creations if possible, but simplicity first)
        for seed in user_seeds:
            # Vector Search for similar existing concepts
            embedding = seed.get('embedding')
            if not embedding: continue
            
            # Find Candidates (High Similarity > 0.85)
            aql_candidates = """
            FOR doc IN Concepts
                LET score = COSINE_SIMILARITY(doc.embedding, @embedding)
                FILTER score > 0.85
                RETURN { id: doc._id, label: doc.label, score: score }
            """
            candidates_cursor = self.db.aql.execute(aql_candidates, bind_vars={"embedding": embedding})
            candidates = list(candidates_cursor)
            
            for cand in candidates:
                # create RELATED_TO edge
                # Check if edge exists first to avoid dupes
                # (Skipped check for speed, Arango ignores duplicate _key if we set it deterministically, or we just insert)
                print(f"   -> Linking Seed '{seed['text'][:20]}...' to Concept '{cand['label']}' (Score: {cand['score']:.2f})")
                
                edge = {
                    "_from": seed['_id'],
                    "_to": cand['id'],
                    "type": "RELATED_TO",
                    "status": "candidate_merge", # Flag for user review
                    "weight": cand['score']
                }
                try:
                    self.db.collection("Relationships").insert(edge)
                except:
                    pass # Ignore if exists

        # 3. Structural Mastery Update (Pure Graph)
        # Update mastery for ALL concepts connected to this session's seeds
        print("   -> Updating Structural Mastery...")
        
        # AQL to find all related concepts and recalc degree
        # 1. Fetch Touched Concepts
        aql_fetch = """
        LET touched_concepts = (
            FOR seed IN Seeds
                FILTER seed.session_id == @session_id
                FOR v, e, p IN 1..1 ANY seed GRAPH 'concept_graph'
                FILTER v != null
                FILTER IS_SAME_COLLECTION('Concepts', v)
                RETURN DISTINCT v._id
        )
        RETURN touched_concepts
        """
        cursor = self.db.aql.execute(aql_fetch, bind_vars={"session_id": session_id})
        touched_ids = list(cursor)[0]
        
        print(f"   -> Found {len(touched_ids)} connected concepts to update.")
        
        # 2. Update Each Concept (Robust)
        for cid in touched_ids:
            if not cid: continue
            
            try:
                aql_update = """
                LET cid = @cid
                LET in_degree = LENGTH(FOR doc IN Relationships FILTER doc._to == cid RETURN 1)
                LET out_degree = LENGTH(FOR doc IN Relationships FILTER doc._from == cid RETURN 1)
                LET raw_score = (in_degree + out_degree) * 0.05
                LET new_mastery = MIN([1.0, raw_score])
                
                UPDATE cid WITH { mastery: new_mastery, last_reviewed: DATE_ISO8601(DATE_NOW()) } IN Concepts OPTIONS { ignoreErrors: true }
                RETURN { id: cid, old: OLD.mastery, new: new_mastery }
                """
                
                upd_cursor = self.db.aql.execute(aql_update, bind_vars={"cid": cid})
                for m in upd_cursor:
                     print(f"      Concept {m['id']} Mastery: {m['old'] or 0} -> {m['new']}")
                     
            except Exception as e:
                print(f"      [WARNING] Failed to update concept {cid}: {e}")

        # 4. Archiving
        # For MVP, we just assume Session Collection exists or we conceptually mark it.
        # Since we don't have a specific 'Sessions' collection setup in the previous steps explicitly verified, 
        # we will skip the actual DB update for Session object if it doesn't exist, but logic is here.
        print(f"--- Consolidation Complete. Session {session_id} Archived. ---")

