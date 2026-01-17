from typing import List, Dict, Optional, Tuple
from fastembed import TextEmbedding
from backend.app.db.arango import db
import datetime
import json
import re
from backend.app.services.llm import get_llm
from backend.app.core.prompts import prompts
from langchain_core.messages import HumanMessage, SystemMessage
from backend.app.core.rate_limiter import global_limiter
from fuzzywuzzy import fuzz

# Lazy load reranker to avoid slow startup
_reranker_model = None

def get_reranker():
    """Lazy load the cross-encoder reranker model."""
    global _reranker_model
    if _reranker_model is None:
        try:
            from sentence_transformers import CrossEncoder
            # ms-marco-MiniLM is fast and effective for reranking
            _reranker_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
            print("[Phase 14] Reranker loaded: cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            print(f"[Phase 14] Reranker not available: {e}")
            _reranker_model = False  # Mark as unavailable
    return _reranker_model if _reranker_model else None


class GraphRAGService:
    def __init__(self):
        # Initialize FastEmbed for embeddings (bge-small for compatibility with existing DB)
        # Note: BGE-M3 (1024 dims) can be used for new deployments, but requires re-embedding
        self.embedding_model = TextEmbedding("BAAI/bge-small-en-v1.5")  # 384 dims
        self.db = db.get_db()
        
        # Reranker config
        self.RERANK_ENABLED = True
        self.RERANK_TOP_K = 20  # Retrieve more, then rerank
        self.RERANK_FINAL_K = 10  # Return top after reranking

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for text using FastEmbed."""
        # FastEmbed returns a generator, consume it
        return list(self.embedding_model.embed([text]))[0]
    
    def rerank_results(self, query: str, results: List[Dict], top_k: int = 10) -> List[Dict]:
        """
        Phase 14: Rerank results using cross-encoder for better precision.
        
        Args:
            query: Original user query
            results: List of retrieved results (concepts/seeds)
            top_k: Number of top results to return after reranking
            
        Returns:
            Reranked list of results
        """
        if not results or not self.RERANK_ENABLED:
            return results[:top_k]
        
        reranker = get_reranker()
        if not reranker:
            return results[:top_k]
        
        try:
            # Prepare query-document pairs for cross-encoder
            pairs = []
            for r in results:
                # Extract text from concept or seed
                if 'concept' in r:
                    doc_text = f"{r['concept'].get('label', '')} {r['concept'].get('definition', '')}"
                elif 'seed' in r:
                    doc_text = r['seed'].get('highlight', '') or r['seed'].get('content', '')
                elif 'doc' in r:
                    doc_text = r['doc'].get('highlight', '') or r['doc'].get('content', '')
                else:
                    doc_text = str(r)
                
                pairs.append((query, doc_text[:500]))  # Truncate for speed
            
            # Get reranking scores
            scores = reranker.predict(pairs)
            
            # Attach rerank scores and sort
            for i, r in enumerate(results):
                r['rerank_score'] = float(scores[i])
            
            # Sort by rerank score (higher = more relevant)
            reranked = sorted(results, key=lambda x: x.get('rerank_score', 0), reverse=True)
            
            print(f"[Phase 14] Reranked {len(results)} results -> top {top_k}")
            return reranked[:top_k]
            
        except Exception as e:
            print(f"[Phase 14] Reranking failed: {e}")
            return results[:top_k]

    async def create_session(self, title: str, goal: str) -> str:
        """
        Creates a new Session document with TTL.
        """
        import uuid
        import datetime
        
        session_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.UTC)
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

    async def list_sessions(self) -> List[Dict]:
        """
        Returns all sessions, sorted by creation date (newest first).
        """
        if not self.db.has_collection("Sessions"):
            return []
            
        aql = """
        FOR s IN Sessions
            SORT s.created_at DESC
            LET concept_count = LENGTH(
                FOR v, e IN 1..1 OUTBOUND s GRAPH 'concept_graph'
                RETURN v
            )
            RETURN MERGE(s, { concept_count: concept_count })
        """
        cursor = self.db.aql.execute(aql)
        return [doc for doc in cursor]

    async def delete_session(self, session_id: str) -> bool:
        """
        Permanently deletes a session and its associated data.
        1. Deletes Session Document.
        2. Deletes all Seeds (Evidence) linked to this session.
        3. Deletes all Edges connected to the Session Node.
        """
        try:
            # 1. Delete Session Node
            if self.db.has_collection("Sessions"):
                self.db.collection("Sessions").delete(session_id, ignore_missing=True)
                
            # 2. Delete Seeds (Evidence)
            # AQL is safer for batch deletion
            aql_delete_seeds = """
            FOR doc IN Seeds
                FILTER doc.session_id == @session_id
                REMOVE doc IN Seeds
            """
            self.db.aql.execute(aql_delete_seeds, bind_vars={"session_id": session_id})
            
            # 3. Delete Relationships (Edges)
            # Remove any edge where _from or _to is the session_id
            # Also remove edges where _from or _to was a Seed we just deleted (implicit via Arango/Graph usually, but manual to be safe)
            # For now, just focus on direct Session Connections
            aql_delete_edges = """
            FOR e IN Relationships
                FILTER e._from == @session_id OR e._to == @session_id
                REMOVE e IN Relationships
            """
            self.db.aql.execute(aql_delete_edges, bind_vars={"session_id": f"Sessions/{session_id}"})
            # Note: session_id in edge might form full ID if stored that way. 
            # Usually input session_id is just UUID. Let's try both matches to be robust.
            
            return True
        except Exception as e:
            print(f"Error deleting session {session_id}: {e}")
            raise e

    async def hybrid_search(self, query: str, session_id: str = None, intent: str = "GENERAL", top_k: int = 5, allow_global_fallback: bool = True) -> List[Dict]:
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
            // TRAVERSAL UPGRADE: 1..2 steps (Recursive)
            FOR v, e, p IN 1..2 ANY start_node.doc GRAPH 'concept_graph'
            
            // INTENT-AWARE BOOSTING & FILTERING
            // We want strong logical links, not just "related_to"
            LET is_strong = e.type IN ['CAUSES', 'REQUIRES', 'PART_OF', 'CONTRADICTS', 'ENABLES']
            
            LET boost = 
                (@intent == 'FACT_CHECK' AND e.type == 'CONTRADICTS') ? 2.5 : 
                (@intent == 'LEARNING' AND e.type == 'PREREQUISITE') ? 2.0 : 
                is_strong ? 1.5 :
                1.0
                
            SORT boost DESC
            LIMIT 20 // Don't overwhelm context
            
            RETURN DISTINCT { doc: v, score: 0.5 * boost, type: 'graph_neighbor', edge_type: e.type }
        )
        
        // Merge and Deduplicate
        RETURN UNION(vector_results, graph_results)
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
        # ONLY if allowed
        if allow_global_fallback and len(session_results) < 3:
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

    async def ingest_document(self, content: str, metadata: Dict, extract_concepts: bool = False):
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

        # 3. Aggressive Ingestion: Extract Concepts Immediately
        # Only if flag is True (False when batching externally)
        if extract_concepts:
            # Use the "Best-in-Class" Legacy Prompt
            print(f"--- Starting Immediate Extraction for {source_name} ---")
            try:
                 extract_content = content[:30000]
                 session_id = metadata.get("session_id")
                 extraction_result = await self.extract_session_concepts(extract_content, doc_id=source_id)
                 
                 if extraction_result and "concepts" in extraction_result:
                     print(f"Extracted {len(extraction_result['concepts'])} concepts.")
                     await self._store_extraction_results(extraction_result, source_id, session_id)

            except TypeError as e:
                print(f"CRITICAL: Method signature mismatch in extraction: {e}")
            except Exception as e:
                print(f"Error during immediate extraction: {e}") 

    async def process_batch_extraction(self, full_text: str, source_name: str, session_id: str = None):
        """
        Batched Extraction: Splits text into large chunks (15k-20k) to maximize LLM context window
        and minimize calls.
        """
        source_id = await self._ensure_source_node(source_name)
        BATCH_SIZE = 30000
        overlap = 1000
        
        total_len = len(full_text)
        print(f"--- Starting Batch Extraction for {source_name} (Length: {total_len}) ---")
        
        for start in range(0, total_len, BATCH_SIZE - overlap):
            end = min(start + BATCH_SIZE, total_len)
            chunk_text = full_text[start:end]
            
            print(f"Processing batch {start}-{end}...")
            try:
                extraction_result = await self.extract_session_concepts(chunk_text, doc_id=source_id)
                if extraction_result and "concepts" in extraction_result:
                     print(f"Extracted {len(extraction_result['concepts'])} concepts from batch.")
                     await self._store_extraction_results(extraction_result, source_id, session_id)
                     
            except Exception as e:
                print(f"Error processing batch {start}: {e}")
            
            if end >= total_len:
                break
            
            # Rate Limit Protection: Wait 5 seconds between batches
            import asyncio
            print("Throttling: Waiting 5s to respect Rate Limits...")
            await asyncio.sleep(5)


    async def extract_session_concepts(self, text_block: str, doc_id: str = "unknown") -> Dict:
        """
        Uses the 'Best-in-Class' Legacy Prompt to extract rich concepts.
        """
        # SAFEGUARD: If text extraction failed (empty PDF/image), 
        # do NOT call LLM, or it will hallucinate based on System Prompt.
        if not text_block or len(text_block.strip()) < 50:
            print(f"Skipping Extraction: Text block too short ({len(text_block) if text_block else 0} chars). content: '{text_block}'")
            return {}

        llm = get_llm()
        
        # The Legacy Prompt (Ported from extract_prompt_2.txt)
        # The Legacy Prompt (Ported from extract_prompt_2.txt)
        prompt_text = prompts.get("extraction", doc_id=doc_id, text_block=text_block)
        
        # LOGGING PROMPT (User Request)
        try:
            with open("d:\\major_project\\log.txt", "a", encoding="utf-8") as f:
                f.write(f"\n\n--- [PROMPT] {datetime.datetime.now().isoformat()} ---\n{prompt_text}\n----------------------------------\n")
        except Exception as e:
            print(f"Log Error: {e}")

        # Rate Limit Check
        await global_limiter.wait_for_token()

        max_retries = 5
        base_delay = 2

        for attempt in range(max_retries):
            try:
                response = await llm.ainvoke([HumanMessage(content=prompt_text)])
                content = response.content.strip()
                
                # LOGGING RESPONSE (User Request)
                try:
                    with open("d:\\major_project\\log.txt", "a", encoding="utf-8") as f:
                        f.write(f"\n--- [RESPONSE] {datetime.datetime.now().isoformat()} ---\n{content}\n==================================\n")
                except Exception as e:
                    print(f"Log Error: {e}")
                
                print(f"DEBUG: Raw LLM Response (First 500 chars): {content[:500]}") # DEBUGGING

                # Clean JSON markdown if present
                content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
                
                return json.loads(content)
            
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "rate limit" in error_str:
                    delay = base_delay * (2 ** attempt)
                    print(f"WARNING: LLM Rate Limit (429). Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                    import asyncio
                    await asyncio.sleep(delay)
                    # Refund token? No, we consumed a request that failed. Just try again.
                    # Wait for token again before retrying?
                    await global_limiter.wait_for_token()
                else:
                    # Non-retriable error
                    print(f"LLM Extraction failed: {e}")
                    return {}
        
        print(f"ERROR: Max retries exceeded for doc {doc_id}. Skipping.")
        return {}

    async def _store_extraction_results(self, data: Dict, source_id: str, session_id: str = None):
        """
        Writes the rich extracted data to ArangoDB.
        """
        if not data or "concepts" not in data: return

        print(f"Storing {len(data['concepts'])} concepts...")
        
        # 1. Ensure Collections Exist
        if not self.db.has_collection("Concepts"):
            self.db.create_collection("Concepts")
            
        if not self.db.has_collection("Relationships"):
            self.db.create_collection("Relationships", edge=True)
            
        if session_id and not self.db.has_collection("ConceptSessionLinks"):
             self.db.create_collection("ConceptSessionLinks", edge=True)

        # 2. Ensure Session Node if exists
        if session_id:
             # Basic upsert for session node to ensure it exists
             self.db.collection("Sessions").insert({"_key": session_id, "type": "session"}, overwrite=True)

        for concept in data["concepts"]:
            # Sanitize Key
            key = re.sub(r"[^a-zA-Z0-9_-]", "_", concept["name"]).lower()
            
            # Prepare Doc
            doc = {
                "_key": key,
                "label": concept["name"], # Use 'label' for visualization
                "name": concept["name"],
                "type": "concept", # Standard type
                "concept_type": concept.get("concept_type", "Concept"),
                "definition": concept.get("operational_details", {}).get("implementation_steps", [""])[0] if concept.get("operational_details") else "",
                "operational_details": concept.get("operational_details", {}),
                "contextual_examples": concept.get("contextual_examples", {}),
                "sub_concepts_raw": concept.get("sub_concepts", []), # Store raw for now
                "domain": data.get("domain", "General"),
                "created_at": datetime.datetime.utcnow().isoformat(),
                "val": 10 # Importance boost for these high-quality nodes
            }
            
            # Upsert Concept - Smart Merge (Update)
            # overwrite_mode='update' ensures we merge new fields into existing ones
            # instead of replacing the whole document.
            self.db.collection("Concepts").insert(doc, overwrite_mode='update')
            
            # Link to Source
            self.db.collection("Relationships").insert({
                "_from": source_id, 
                "_to": f"Concepts/{key}",
                "type": "MENTIONS",
                "created_at": datetime.datetime.utcnow().isoformat()
            })
            
            # Link to Session
            if session_id:
                self.db.collection("ConceptSessionLinks").insert({
                    "_from": f"Concepts/{key}",
                    "_to": f"Sessions/{session_id}",
                    "relation": "CREATED_IN",
                    "created_at": datetime.datetime.utcnow().isoformat()
                })
                
            # Process Relations
            for rel in concept.get("relations", []):
                target_key = re.sub(r"[^a-zA-Z0-9_-]", "_", rel["target"]).lower()
                # We can't guarantee target exists yet. 
                # Strategy: Insert "Stub" for target? Or just ignore?
                # Better: Insert Stub.
                # Strategically Insert Stub: Ignore if exists (keep original rich node)
                try:
                    self.db.collection("Concepts").insert({
                        "_key": target_key, 
                        "label": rel["target"], 
                        "type": "concept", 
                        "stub": True
                    }, overwrite=False) 
                except Exception:
                    # Ignore 409 (Duplicate) - Node exists, likely richer than our stub
                    pass
                
                # Create Edge
                edge_type = rel.get("type", "RELATED_TO").upper().replace("-", "_")
                self.db.collection("Relationships").insert({
                    "_from": f"Concepts/{key}",
                    "_to": f"Concepts/{target_key}",
                    "type": edge_type,
                    "note": rel.get("note", ""),
                    "confidence": "high" if rel.get("strength") == "strong" else "medium"
                })

            # Process Sub-Concepts (Granularity Expansion)
            for sub in concept.get("sub_concepts", []):
                sub_name = sub.get("name")
                if not sub_name: continue

                sub_key = re.sub(r"[^a-zA-Z0-9_-]", "_", sub_name).lower()
                
                # Upsert Sub-Concept Node
                sub_doc = {
                    "_key": sub_key,
                    "label": sub_name,
                    "name": sub_name,
                    "type": "sub_concept", # Distinct type for filtering/visuals
                    "definition": sub.get("explanation", ""),
                    "sub_type": sub.get("sub_type", "Component"),
                    "created_at": datetime.datetime.utcnow().isoformat(),
                    "val": 5 # Smaller visual size
                }
                
                # Careful Upsert: Don't overwrite if it exists as a full concept
                try:
                    self.db.collection("Concepts").insert(sub_doc, overwrite_mode='update')
                except Exception:
                    pass

                # Link Parent -> Sub-Concept (HAS_PART)
                self.db.collection("Relationships").insert({
                    "_from": f"Concepts/{key}",
                    "_to": f"Concepts/{sub_key}",
                    "type": "HAS_PART",
                    "created_at": datetime.datetime.utcnow().isoformat()
                })

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
            prompt = prompts.get("conflict_detection", seed_text=seed['text'], target_text=target_text)
            
            await global_limiter.wait_for_token()
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
        Phase 8: Hybrid Entity Resolution.
        1. Find Concepts created in this session.
        2. Compare against Global Graph (Vector + Fuzzy + LLM).
        3. Merge or Link.
        4. Archive Session.
        """
        print(f"--- Starting Hybrid Consolidation for Session: {session_id} ---")
        
        # 1. Identify Concepts created in this session
        # We find them via the edges created during extraction
        session_node_id = f"Sessions/{session_id}"
        
        aql_concepts = """
        FOR link IN ConceptSessionLinks
            FILTER link._to == @session_node_id
            RETURN DOCUMENT(link._from)
        """
        cursor = self.db.aql.execute(aql_concepts, bind_vars={"session_node_id": session_node_id})
        new_concepts = list(cursor)
        
        if not new_concepts:
            print("No new concepts to consolidate.")
        else:
            print(f"Processing {len(new_concepts)} new concepts for resolution...")

            for concept in new_concepts:
                if not concept: continue
                # Safety Check: Ensure embedding exists
                if 'embedding' not in concept or not concept['embedding']:
                    print(f"   Skipping resolution for '{concept.get('label','?')}' (No Embedding)")
                    continue
                
                # 2. Vector Search for Candidates (excluding self)
                aql_candidates = """
                FOR doc IN Concepts
                    FILTER doc._id != @concept_id
                    LET score = COSINE_SIMILARITY(doc.embedding, @embedding)
                    FILTER score > 0.85
                    SORT score DESC
                    LIMIT 5
                    RETURN { id: doc._id, label: doc.label, definition: doc.definition, score: score }
                """
                
                candidates_cursor = self.db.aql.execute(aql_candidates, bind_vars={
                    "concept_id": concept['_id'],
                    "embedding": concept['embedding']
                })
                candidates = list(candidates_cursor)
                
                merged = False
                for cand in candidates:
                    if merged: break
                    
                    # 3. Hybrid Judge Logic
                    # Calculate Fuzzy Ratio
                    label_a = concept.get('label', '').lower()
                    label_b = cand['label'].lower()
                    fuzzy_score = fuzz.ratio(label_a, label_b)
                    
                    is_match = False
                    reason = "Hybrid Logic"
                    
                    print(f"   Checking: '{concept['label']}' vs '{cand['label']}' (Vector: {cand['score']:.2f}, Fuzzy: {fuzzy_score})")

                    if cand['score'] > 0.98:
                         # Case A: Aggressive Vector Auto-Merge
                         is_match = True
                         reason = f"High Vector Score ({cand['score']:.3f})"

                    elif fuzzy_score > 90:
                        # Case B: High Fuzzy -> Auto Merge
                        is_match = True
                        reason = f"High Fuzzy Score ({fuzzy_score})"
                    
                    elif cand['score'] > 0.85: 
                        # Case C: Ambiguous Middle Ground (High Vector, Low Fuzzy) -> LLM Judge
                        print("   -> Invoking LLM Judge (Ambiguous)...")
                        is_match, reason = await self._llm_merge_judge(concept, cand)
                    
                    if is_match:
                        print(f"   MATCH FOUND! Merging {concept['label']} -> {cand['label']} ({reason})")
                        await self._merge_concepts(source_id=concept['_id'], target_id=cand['id'])
                        merged = True
                    else:
                        # If not a match, but High Vector, make sure they are linked?
                        # Using _form_synapses logic implicitly for new concepts later, 
                        # but we can add a quick link here if score > 0.88?
                        # Let's keep it simple for now to avoid noise.
                        pass

        # 4. Form Synapses (Auto-Association)
        await self._form_synapses(new_concepts, session_id)

        # 5. Crystalize
        self.db.aql.execute("""
            UPDATE @key WITH { status: 'crystallized', finalized_at: DATE_ISO8601(DATE_NOW()) } IN Sessions
        """, bind_vars={"key": session_id})
        
        return {"status": "success", "message": "Session Crystallized with Hybrid Resolution"}

    async def _llm_merge_judge(self, concept_a: Dict, concept_b: Dict) -> (bool, str):
        """
        Asks the LLM if two concepts are semantically identical.
        """
        llm = get_llm()
        prompt = prompts.get("merge_judge", 
            concept_a=concept_a.get('label'), def_a=concept_a.get('definition', ''),
            concept_b=concept_b['label'], def_b=concept_b.get('definition', '')
        )
        
        try:
            await global_limiter.wait_for_token()
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip().replace("```json", "").replace("```", "")
            data = json.loads(content)
            return data.get("is_same", False), data.get("reason", "LLM Decision")
        except Exception as e:
            print(f"LLM Judge Error: {e}")
            return False, "Error"

    async def _merge_concepts(self, source_id: str, target_id: str):
        """
        Merges Source Node INTO Target Node.
        1. Move all Edges (In/Out) from Source to Target.
        2. Delete Source Node.
        """
        # AQL to move edges
        # We need to handle 'from' edges and 'to' edges
        
        # 1. Move Outgoing Edges (Source -> X) ==> (Target -> X)
        # Avoid duplicate edges if Target -> X already exists
        aql_move_out = """
        FOR e IN Relationships
            FILTER e._from == @source_id
            // Check if equivalent edge exists
            LET exists = FIRST(
                FOR te IN Relationships
                    FILTER te._from == @target_id AND te._to == e._to AND te.type == e.type
                    RETURN 1
            )
            FILTER exists == null
            // Re-create edge
            INSERT { _from: @target_id, _to: e._to, type: e.type, created_at: e.created_at, merged_from: @source_id } INTO Relationships
        """
        self.db.aql.execute(aql_move_out, bind_vars={"source_id": source_id, "target_id": target_id})
        
        # 2. Move Incoming Edges (X -> Source) ==> (X -> Target)
        aql_move_in = """
        FOR e IN Relationships
            FILTER e._to == @source_id
             // Check if equivalent edge exists
            LET exists = FIRST(
                FOR te IN Relationships
                    FILTER te._to == @target_id AND te._from == e._from AND te.type == e.type
                    RETURN 1
            )
            FILTER exists == null
            INSERT { _from: e._from, _to: @target_id, type: e.type, created_at: e.created_at, merged_from: @source_id } INTO Relationships
        """
        self.db.aql.execute(aql_move_in, bind_vars={"source_id": source_id, "target_id": target_id})
        
        # 3. Delete Source Node and its old edges
        # Delete edges explicitly or let Arango graph handle?
        # AQL REMOVE on edges is safest.
        self.db.aql.execute("FOR e IN Relationships FILTER e._from == @id OR e._to == @id REMOVE e IN Relationships", bind_vars={"id": source_id})
        
        # Also remove from ConceptSessionLinks
        if self.db.has_collection("ConceptSessionLinks"):
             self.db.aql.execute("FOR e IN ConceptSessionLinks FILTER e._from == @id OR e._to == @id REMOVE e IN ConceptSessionLinks", bind_vars={"id": source_id})
             
        # Delete Node
        self.db.collection("Concepts").delete(source_id, ignore_missing=True)
        print(f"   -> Merged {source_id} into {target_id}")



    async def get_session_summary(self, session_id: str) -> Dict:
        """
        Aggregates all session data for the Final Report.
        """
        # 1. Fetch Session Metadata
        aql_session = """
        FOR doc IN Sessions
            FILTER doc._key == @session_id
            RETURN doc
        """
        session_cursor = self.db.aql.execute(aql_session, bind_vars={"session_id": session_id})
        session_docs = list(session_cursor)
        
        session = None
        if session_docs:
            session = session_docs[0]
        
        # 2. Fetch Seeds (Evidence) - Do this EARLY to check for orphans
        aql_seeds = """
        FOR doc IN Seeds
            FILTER doc.session_id == @session_id OR doc.session_id == @session_key
            SORT doc.created_at ASC
            RETURN doc
        """
        seeds_cursor = self.db.aql.execute(aql_seeds, bind_vars={"session_id": session_id, "session_key": session_id})
        seeds = list(seeds_cursor)
        
        # Checking for Orphaned Session (Evidence exists, but Session Node missing)
        if not session:
            if seeds:
                print(f"WARNING: Session {session_id} Doc missing, but {len(seeds)} seeds found. Auto-healing...")
                # Auto-Heal: Create Session Doc
                import datetime
                session = {
                    "_key": session_id,
                    "title": "Recovered Session",
                    "goal": "Auto-healed from Evidence",
                    "created_at": datetime.datetime.utcnow().isoformat(),
                    "status": "active"
                }
                self.db.collection("Sessions").insert(session)
            else:
                # Truly Not Found
                return None
        
        # 3. Fetch UserSeeds (Thoughts)
        
        # 3. Fetch UserSeeds (Thoughts)
        aql_user_seeds = """
        FOR doc IN UserSeeds
            FILTER doc.session_id == @session_id OR doc.session_id == @session_key
            SORT doc.created_at ASC
            RETURN doc
        """
        user_seeds_cursor = self.db.aql.execute(aql_user_seeds, bind_vars={"session_id": session_id, "session_key": session_id})
        user_seeds = list(user_seeds_cursor)
        
        # 4. Construct Temporal Log
        events = []
        
        # Group seeds by source to avoid timeline bloat
        from itertools import groupby
        
        def group_key(s): return s.get('source', 'Unknown')
        sorted_seeds = sorted(seeds, key=group_key)
        
        for source, group in groupby(sorted_seeds, key=group_key):
             group_list = list(group)
             first_seed = group_list[0]
             count = len(group_list)
             
             if count > 1:
                 # Collapsed Event
                 events.append({
                    "type": "evidence",
                    "id": first_seed["_id"],
                    "content": f"Uploaded {source.split('/')[-1]} ({count} chunks processed)",
                    "full_content": "\n\n...\n\n".join([s.get("highlight", "") for s in group_list[:3]]) + f"\n\n(+ {count-3} more chunks)",
                    "timestamp": first_seed.get("created_at"),
                    "source": source
                 })
             else:
                 # Single Chunk Event
                 events.append({
                    "type": "evidence",
                    "id": first_seed["_id"],
                    "content": first_seed.get("highlight", "")[:100] + "...",
                    "full_content": first_seed.get("highlight", ""),
                    "timestamp": first_seed.get("created_at"),
                    "source": source
                 })
            
        for u in user_seeds:
            events.append({
                "type": "thought",
                "id": u["_id"],
                "content": u.get("text", ""),
                "full_content": u.get("text", ""),
                "timestamp": u.get("created_at"),
                "confidence": u.get("confidence", "Medium")
            })
            
        # 5. Fetch Graph Data (Nodes + Edges)
        # Architecture Upgrade: Continuous Extraction
        # ... (Extraction Logic) ...
        
        # NOTE: Moving extraction logic UP to before timeline construction 
        # so we can include the analysis IN the timeline.
        
        # Check if we have extracted concepts for this session
        aql_check_concepts = """
        FOR doc IN UserSeeds
            FILTER doc.session_id == @session_id AND doc.type == 'extracted_concept'
            RETURN doc
        """
        existing_concepts = list(self.db.aql.execute(aql_check_concepts, bind_vars={"session_id": session_id}))
        
        extracted_concepts = []
        extracted_relationships = []
        
        if not existing_concepts and events:
             try:
                 # Lazy Load: Trigger Extraction
                 evidence_texts = [e['full_content'] for e in events if e['type'] == 'evidence']
                 
                 if evidence_texts:
                     print(f"DEBUG: Lazy Extracting Concepts for Session {session_id}...")
                     
                     # BATCHING LOGIC
                     full_evidence = "\n\n".join(evidence_texts)
                     # Limit total processing to avoid timeout?
                     # Let's verify length.
                     print(f"DEBUG: Total Evidence Length: {len(full_evidence)}")
                     
                     BATCH_SIZE = 50000
                     chunks = [full_evidence[i:i+BATCH_SIZE] for i in range(0, len(full_evidence), BATCH_SIZE)]
                     
                     all_concepts = []
                     all_relationships = []
                     
                     for i, chunk in enumerate(chunks):
                         print(f"--- Processing Batch {i+1}/{len(chunks)} ---")
                         try:
                             result = await self.extract_session_concepts(chunk)
                             if result:
                                 batch_concepts = result.get("concepts", [])
                                 batch_rels = result.get("relationships", []) 
                                 
                                 # Normalize nested relations
                                 if not batch_rels:
                                     for c in batch_concepts:
                                         c_name = c.get('name') or c.get('label')
                                         for r in c.get('relations', []):
                                             batch_rels.append({
                                                 "source": c_name,
                                                 "target": r.get('target'),
                                                 "relation": r.get('type')
                                             })

                                 all_concepts.extend(batch_concepts)
                                 all_relationships.extend(batch_rels)
                         except Exception as e:
                             print(f"Error extracting batch {i}: {e}")
                             import traceback
                             traceback.print_exc()

                     # Deduplicate Concepts
                     unique_concepts = {}
                     for c in all_concepts:
                         name = c.get('name') or c.get('label')
                         if name and name not in unique_concepts:
                             unique_concepts[name] = c
                             
                     extracted_data = list(unique_concepts.values())
                     
                     # Deduplicate Relationships
                     unique_rels = {}
                     for r in all_relationships:
                         key = (r.get('source'), r.get('target'), r.get('relation'))
                         if key[0] and key[1] and key not in unique_rels:
                             unique_rels[key] = r
                             
                     relationships_data = list(unique_rels.values())

                     import datetime
                     # 1. Save Concepts
                     concept_map = {} 
                     for c in extracted_data:
                         label = c.get('name') or c.get('label', 'Unknown Concept')
                         
                         definition = c.get('definition', "")
                         if not definition and c.get('operational_details'):
                             steps = c.get('operational_details', {}).get("implementation_steps", [])
                             definition = steps[0] if steps else ""
                         
                         # Embed might fail?
                         emb = []
                         try:
                             emb = self.embed_query(label).tolist()
                         except Exception as e:
                             print(f"Embedding failed for {label}: {e}")

                         doc = {
                             "text": c.get("text") or f"{label}: {definition}",
                             "label": label,
                             "definition": definition,
                             "type": "extracted_concept",
                             "session_id": session_id,
                             "created_at": datetime.datetime.utcnow().isoformat(),
                             "embedding": emb
                         }
                         meta = self.db.collection("UserSeeds").insert(doc)
                         doc["_id"] = meta["_id"]
                         extracted_concepts.append(doc)
                         concept_map[label] = meta["_id"]
                         
                     # 2. Save Relationships 
                     for r in relationships_data:
                         if r['source'] in concept_map and r['target'] in concept_map:
                             rel_doc = {
                                 "source_id": concept_map[r['source']],
                                 "target_id": concept_map[r['target']],
                                 "relation": r['relation'],
                                 "type": "extracted_relation",
                                 "session_id": session_id,
                                 "created_at": datetime.datetime.utcnow().isoformat()
                             }
                             self.db.collection("UserSeeds").insert(rel_doc)
                             extracted_relationships.append(rel_doc)
             except Exception as e:
                 print(f"CRITICAL ERROR in Defered Extraction: {e}")
                 import traceback
                 traceback.print_exc()
                 # Do not re-raise to avoid 500. Return partial.
                 pass
                         
        else:
            extracted_concepts = existing_concepts
            # Fetch existing relationships
            aql_rels = """
            FOR doc IN UserSeeds
                FILTER doc.session_id == @session_id AND doc.type == 'extracted_relation'
                RETURN doc
            """
            extracted_relationships = list(self.db.aql.execute(aql_rels, bind_vars={"session_id": session_id}))

        # Inject Analysis Event into Timeline if we have concepts
        if extracted_concepts:
            # Create a summary string
            concept_list = "\n".join([f"• {c['label']}: {c['definition']}" for c in extracted_concepts])
            
            rel_list = ""
            if extracted_relationships:
                # Need to map IDs back to labels for display if we loaded from DB
                # Quick lookup map
                id_to_label = { c['_id']: c['label'] for c in extracted_concepts }
                
                rel_lines = []
                for r in extracted_relationships:
                     s_lbl = id_to_label.get(r['source_id'], '?')
                     t_lbl = id_to_label.get(r['target_id'], '?')
                     rel_lines.append(f"• {s_lbl} --[{r['relation']}]--> {t_lbl}")
                
                if rel_lines:
                    rel_list = "\n\nRelationships:\n" + "\n".join(rel_lines[:5]) # Show top 5

            summary_text = f"Analyzed Session Evidence.\n\nKey Concepts:\n{concept_list}{rel_list}"
            
            # Find the timestamp of the last evidence event to place this after
            last_evidence_time = events[-1]['timestamp'] if events else None
            
            events.append({
                "type": "analysis", 
                "id": "analysis-summary",
                "content": summary_text,
                "full_content": summary_text,
                "timestamp": last_evidence_time, 
                "source": "AI Assistant"
            })

        # Sort by timestamp
        events.sort(key=lambda x: x["timestamp"] or "")

        # Format Nodes for Graph
        graph_nodes = []
        
        # Evidence Nodes (Orange)
        for s in seeds:
            # Try to find page info in various common keys
            page = s.get("page") or s.get("page_label") or s.get("page_number")
            source_label = s.get("source", "Evidence")
            if page:
                source_label = f"{source_label} (Page {page})"
                
            graph_nodes.append({
                "id": s["_id"], 
                "label": "Evidence", 
                "group": "evidence", 
                "color": "orange", 
                "val": 3, 
                "title": source_label,
                "content": s.get("highlight", "") # Pass actual text!
            })
            
        # Thought Nodes (Purple)
        for u in user_seeds:
            if u.get('type') not in ['extracted_concept', 'extracted_relation']:
                graph_nodes.append({
                    "id": u["_id"], 
                    "label": "Thought", 
                    "group": "thought", 
                    "color": "purple", 
                    "val": 5, 
                    "title": u.get("label", "Thought"),
                    "content": u.get("text", "") 
                })
        
        # Extracted Concept Nodes (Blue)
        for c in extracted_concepts:
            graph_nodes.append({
                "id": c["_id"], 
                "label": c.get("label", "Concept"), 
                "group": "concept", 
                "color": "#3b82f6", 
                "val": 8,
                "title": c.get("definition", ""),
                "content": c.get("definition", ""),
                "category": c.get("type", "Concept") # Pass category for coloring
            })
            
        # Edges
        edges = []
        
        # 1. Extracted Relationships (Concept <-> Concept)
        for r in extracted_relationships:
            edges.append({
                "source": r['source_id'],
                "target": r['target_id'],
                "label": r.get('relation', 'related')
            })
            
        # 2. Dynamic Linking (Evidence <-> Concept)
        if extracted_concepts and seeds:
            for s in seeds:
                # Find closest concept
                best_c = None
                max_sim = -1
                s_emb = s.get('embedding')
                if not s_emb: continue
                
                for c in extracted_concepts:
                    c_emb = c.get('embedding')
                    if c_emb:
                        import numpy as np
                        sim = np.dot(s_emb, c_emb)
                        if sim > max_sim:
                            max_sim = sim
                            best_c = c
                            
                if best_c and max_sim > 0.6: 
                     edges.append({
                         "source": s["_id"],
                         "target": best_c["_id"],
                         "label": "relevant_to"
                     })

        return {
            "session_id": session_id,
            "title": session.get("title", "Untitled Session"),
            "goal": session.get("goal", ""),
            "created_at": session.get("created_at"),
            "timeline": events,
            "concept_count": len(extracted_concepts) + len(user_seeds),
            "evidence_count": len(seeds),
            "graph_data": {
                "nodes": graph_nodes,
                "links": edges
            }
        }

    # --- Phase 12: Generative Scaffolding ---
    
    async def generate_scaffold(self, concept_id: str) -> Dict:
        """
        Generate or retrieve cached 4-format scaffold for a concept.
        Lazy generation: Only generates on first request.
        
        Returns:
            {
                "hands_on": { "language": "python", "content": "..." },
                "visual": { "content": "flowchart TD..." },
                "socratic": { "questions": ["Q1", "Q2", "Q3"] },
                "textual": { "content": "...", "analogy": "..." }
            }
        """
        # 1. Fetch Concept
        # concept_id can be _id (Concepts/xxx) or _key (xxx)
        key = concept_id.split("/")[-1] if "/" in concept_id else concept_id
        
        try:
            concept = self.db.collection("Concepts").get(key)
        except Exception:
            concept = None
        
        if not concept:
            raise ValueError(f"Concept {concept_id} not found")
        
        # 2. Check Cache
        if concept.get("representations"):
            print(f"[Scaffold] Cache HIT for '{concept.get('label')}'")
            return concept["representations"]
        
        print(f"[Scaffold] Generating for '{concept.get('label')}'...")
        
        # 3. Generate via LLM
        llm = get_llm()
        
        prompt = prompts.get("generative_scaffolding",
            concept_label=concept.get("label", "Unknown Concept"),
            concept_definition=concept.get("definition", "No definition available."),
            source_context=concept.get("source_text", "")[:2000]
        )
        
        try:
            await global_limiter.wait_for_token()
            
            response = await llm.ainvoke([
                SystemMessage(content="You are a world-class educator. Output strictly valid JSON."),
                HumanMessage(content=prompt)
            ])
            
            content = response.content.replace("```json", "").replace("```", "").strip()
            representations = json.loads(content)
            
            # 4. Cache in DB + Mark as eligible for spaced repetition
            # Check if this is the first time learning (first_learned not set)
            update_data = {
                "_key": key,
                "representations": representations,
                "scaffold_generated_at": datetime.datetime.utcnow().isoformat(),
                "scaffold_generated": True  # Phase 15: Mark for spaced repetition
            }
            
            # Only set first_learned if not already set (preserve original learning date)
            if not concept.get("first_learned"):
                update_data["first_learned"] = datetime.datetime.utcnow().isoformat()
                # Also initialize next_review to 1 day from now (first review)
                from datetime import timedelta
                update_data["next_review"] = (datetime.datetime.utcnow() + timedelta(days=1)).isoformat()
                update_data["review_count"] = 0
            
            self.db.collection("Concepts").update(update_data)
            
            print(f"[Scaffold] Generated and cached for '{concept.get('label')}'")
            return representations
            
        except json.JSONDecodeError as e:
            print(f"[Scaffold] JSON Parse Error: {e}")
            # Return fallback scaffold
            return {
                "hands_on": {"language": "text", "content": "# Scaffold generation failed. Please try again."},
                "visual": {"content": "flowchart TD\n  A[Error] --> B[Try Again]"},
                "socratic": {"questions": ["What do you already know about this topic?", "What would help you understand it better?", "How might you apply this knowledge?"]},
                "textual": {"content": concept.get("definition", "No definition available."), "analogy": ""}
            }
        except Exception as e:
            print(f"[Scaffold] Generation Error: {e}")
            raise


    async def update_session_content(self, session_id: str, item_id: str, new_content: str):
        """
        Updates the content of a Seed or UserSeed.
        Block updates if session is crystallised.
        """
        # 1. Check Session Status
        aql_status = "RETURN DOCUMENT(CONCAT('Sessions/', @session_id)).status"
        cursor = self.db.aql.execute(aql_status, bind_vars={"session_id": session_id})
        status = cursor.next() if cursor.batch() else None
        
        if status == 'crystallized':
            raise ValueError("Session is Crystallized and cannot be edited.")

        # Determine collection based on ID prefix
        # ID format: Collection/Key
        
        try:
            collection, key = item_id.split('/')
        except ValueError:
            raise ValueError("Invalid ID format. Must be Collection/Key")
        
        if collection not in ["Seeds", "UserSeeds"]:
             raise ValueError("Can only edit Seeds or UserSeeds")
             
        # Update Query
        field_name = 'text' if collection == 'UserSeeds' else 'highlight'
        
        aql = f"""
        UPDATE @key WITH {{ {field_name}: @content }} IN {collection}
        RETURN NEW
        """
        
        cursor = self.db.aql.execute(aql, bind_vars={"key": key, "content": new_content})
        return list(cursor)

    async def preview_crystallization(self, session_id: str) -> Dict:
        """
        Generates a Merge Proposal before committing changes.
        """
        # 1. Fetch Session Concepts (Candidates to Merge)
        # In this simplistic model, we treat UserSeeds as protocol-concepts for now
        # Ideally, we should have intermediate SessionConcepts.
        # We will iterate over UserSeeds and check against Global Concepts.
        
        # We process both UserSeeds (Thoughts) and Seeds (Evidence)
        # 1. Fetch Candidates (Thoughts + Pre-Extracted Concepts)
        # Since we now save Extracted Concepts as UserSeeds with type='extracted_concept',
        # we can just fetch all UserSeeds.
        
        aql_candidates = """
        FOR doc IN UserSeeds
            FILTER doc.session_id == @session_id
            RETURN MERGE(doc, {type: doc.type == 'extracted_concept' ? 'extracted_concept' : 'thought' })
        """
        candidates_to_process = list(self.db.aql.execute(aql_candidates, bind_vars={"session_id": session_id}))
        
        # Logic Check: If no extracted concepts exist yet (e.g. user went straight to Crystallize without viewing report?),
        # trigger extraction now. (Safety fallback)
        has_extracted = any(c.get('type') == 'extracted_concept' for c in candidates_to_process)
        if not has_extracted:
             print("DEBUG: No pre-extracted concepts found. Running fallback extraction...")
             # Fetch evidence text
             aql_evidence_text = """
                FOR doc IN Seeds
                    FILTER doc.session_id == @session_id
                    SORT doc.created_at ASC
                    RETURN doc.highlight
             """
             evidence_texts = list(self.db.aql.execute(aql_evidence_text, bind_vars={"session_id": session_id}))
             if evidence_texts:
                 full_text = "\n\n".join(evidence_texts)[:15000]
                 extracted = await self.extract_session_concepts(full_text)
                 # Add to candidates temporarily (don't save here, save on commit? no, save here for consistency?)
                 # For preview, just use them.
                 candidates_to_process.extend(extracted.get('concepts', []))
        
        # 3. Process Candidates (Link to Global Knowledge)
        merges = []
        new_nodes = []
        conflicts = []
        seen_labels = set()
        
        for seed in candidates_to_process:
            # Determine effective text label
            seed_text = seed.get('label') if seed.get('type') == 'extracted_concept' else seed.get('text')
            if not seed_text or len(seed_text.strip()) < 3: 
                continue
                
            # Dedup within this session's proposal
            normalized_label = seed_text.lower().strip()
            if normalized_label in seen_labels:
                continue
            seen_labels.add(normalized_label)
            
            # Ensure the node has 'text' for the frontend
            if not seed.get('text'):
                seed['text'] = seed_text

            embedding = seed.get('embedding')
            # If extracted concept lacks embedding, generate it on fly
            if not embedding:
                 seed['embedding'] = self.embed_query(seed_text).tolist()
                 embedding = seed['embedding']
                 
            # Find Global Candidates (>0.85 similarity)
            # Exclude current session's seeds to avoid self-match
            print(f"DEBUG: Searching candidates for seed '{seed_text[:30]}...'")
            aql_candidates = """
            FOR doc IN Concepts
                LET score = COSINE_SIMILARITY(doc.embedding, @embedding)
                FILTER score > 0.85
                RETURN { id: doc._id, label: doc.label, score: score, embedding: doc.embedding }
            """
            candidates = list(self.db.aql.execute(aql_candidates, bind_vars={"embedding": embedding}))
            print(f"DEBUG: Found {len(candidates)} candidates.")
            
            if not candidates:
                new_nodes.append(seed)
                continue
                
            # We found candidates.
            # 2. Entity Resolution (with LLM if ambiguous)
            # For MVP, we treat >0.95 as Auto-Merge, 0.85-0.95 as Ambiguous (User Review)
            
            best_match = candidates[0] # Take top 1
            
            if best_match['score'] > 0.95:
                # High Confidence -> Proposed Merge
                merges.append({
                    "source_id": seed['_id'],
                    "target_id": best_match['id'],
                    "target_label": best_match['label'],
                    "confidence": best_match['score'],
                    "status": "auto_merge"
                })
                
                # 3. Conflict Detection (Contextual)
                # Check if new seed contradicts the Concept's existing evidence
                # We can grab a sample of evidence linked to the Concept
                aql_evidence = """
                FOR v, e, p IN 1..1 OUTBOUND @concept_id GRAPH 'concept_graph'
                FILTER IS_SAME_COLLECTION('Seeds', v)
                LIMIT 3
                RETURN v.highlight
                """
                existing_evidence = list(self.db.aql.execute(aql_evidence, bind_vars={"concept_id": best_match['id']}))
                
                if existing_evidence:
                    # Run Conflict Check
                    # We check against the first piece of evidence for now
                    # (In prod, we'd summarize the concept definition)
                    conflict_res = await self.detect_conflicts(seed['text']) 
                    # Note: detect_conflicts checks against UserSeeds, here we want against Concept Evidence.
                    # Reusing logic slightly differently would be better, but staying simple.
                    
                    if conflict_res:
                         conflicts.append({
                             "seed_text": seed['text'],
                             "conflicting_evidence": "Existing Knowledge", # Simplified
                             "reason": conflict_res[0]['reason']
                         })
                         
            else:
                 # Medium Confidence -> Ambiguous
                 merges.append({
                    "source_id": seed['_id'],
                    "target_id": best_match['id'],
                    "target_label": best_match['label'],
                    "confidence": best_match['score'],
                    "status": "ambiguous" # Needs User Approval
                })

        return {
            "session_id": session_id,
            "proposed_merges": merges,
            "new_nodes": new_nodes,
            "conflicts": conflicts
        }

    async def preview_crystallization(self, session_id: str) -> Dict:
        """
        Generates a Preview including Merges, Conflicts, and Synapses using Unified Omni-Batch AI.
        """
        # 1. Fetch Candidates (New Concepts)
        aql_seeds = "FOR doc IN UserSeeds FILTER doc.session_id == @id AND doc.type IN ['concept', 'extracted_concept'] RETURN doc"
        nodes = list(self.db.aql.execute(aql_seeds, bind_vars={"id": session_id}))
        print(f"DEBUG_PREVIEW_OMNI: Found {len(nodes)} nodes for session {session_id}")
        
        # 2. Run ONE Unified Analysis Pass
        analysis_results = await self._analyze_crystallization_batch(nodes, session_id)
        
        return {
            "session_id": session_id,
            "proposed_merges": analysis_results['merges'],
            "conflicts": analysis_results['conflicts'],
            "proposed_synapses": analysis_results['synapses'],
            "new_nodes": nodes # Frontend filters out merged ones usually, or we can refine logic layer
        }

    async def _generate_merge_proposals(self, session_id: str) -> Dict:
        """ Helper for preview logic. """
        # Re-using the logic inside get_session_summary kinda, but we need it explicit.
        # For MVP, we'll fetch existing seeds and run entity resolution check.
        # This is a simplified simulation for V1.
        
        # 1. Fetch Session Seeds (Concept type)
        aql_seeds = "FOR doc IN UserSeeds FILTER doc.session_id == @id AND doc.type IN ['concept', 'extracted_concept'] RETURN doc"
        nodes = list(self.db.aql.execute(aql_seeds, bind_vars={"id": session_id}))
        print(f"DEBUG_PREVIEW_MERGES: Found {len(nodes)} new nodes for session {session_id}")
        
        # 2. Entity Resolution (Propose Merges) - VECTOR ONLY OPTIMIZATION
        merges = []
        final_new_nodes = []
        
        print(f"[{session_id}] Resolving Entities (Vector-Only) for {len(nodes)} extracted concepts...")
        
        for node in nodes:
            # Skip if no embedding
            if 'embedding' not in node or not node['embedding']:
                final_new_nodes.append(node)
                continue
            
            # 2.1 Vector Search
            # We look for the single best match in the Global Graph
            # Thresholds:
            # > 0.92: High Confidence (Almost certainly same)
            # > 0.85: Medium Confidence (Likely same, user should check)
            aql_dup = """
            FOR doc IN Concepts
                LET score = COSINE_SIMILARITY(doc.embedding, @embedding)
                FILTER score > 0.85 
                SORT score DESC
                LIMIT 1
                RETURN { label: doc.label, id: doc._id, definition: doc.definition, score: score }
            """
            cursor = self.db.aql.execute(aql_dup, bind_vars={
                "embedding": node['embedding']
            })
            candidate = next(cursor, None)
            
            is_merged = False
            
            if candidate:
                 score = candidate['score']
                 # Automatic Proposal based on Score
                 # No LLM needed -> User reviews it in Wizard anyway.
                 
                 status = "auto_merge"
                 reason = f"High Vector Similarity ({score:.2f})"
                 
                 if score < 0.92:
                     status = "ambiguous" 
                     reason = f"Moderate Vector Similarity ({score:.2f})"

                 merges.append({
                     "source_id": node['_id'],
                     "source_label": node['label'],
                     "target_id": candidate['id'],
                     "target_label": candidate['label'],
                     "confidence": score,
                     "reason": reason,
                     "status": status
                 })
                 is_merged = True
                 print(f"   -> Proposed Merge ({status}): '{node['label']}' ~= '{candidate['label']}' ({score:.2f})")
            
            if not is_merged:
                final_new_nodes.append(node)

        return {
            "session_id": session_id,
            "proposed_merges": merges, 
            "new_nodes": final_new_nodes,
            "conflicts": []
        }

    async def commit_crystallization(self, session_id: str, approved_merges: List[Dict], new_nodes: List[Dict], approved_synapses: List[Dict] = None):
        """
        Executes the merges and writes new concepts to the Global Graph.
        Archive Session.
        """
        import datetime
        
        # Map for Migrating Edges: UserSeed ID -> Global Concept ID
        seed_to_global_map = {}

        # 1. Process New Nodes -> Create Concepts
        created_concepts = []
        for node in new_nodes:
            # Check if it's already a concept (unlikely in this flow, but good practice)
            # We transform the Seed into a Concept
            label = node.get('label')
            if not label:
                # Naive label extraction: First 5 words of text or highlight
                text_content = node.get('text') or node.get('highlight') or "Untitled Concept"
                label = " ".join(text_content.split()[:5])
                
            concept_doc = {
                "label": label,
                "definition": node.get('text') or node.get('highlight'),
                "embedding": node.get('embedding'), # Persist embedding
                "mastery": 0.1, # Initial mastery
                "next_review": (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat(), # SM-2 Initial
                "created_at": datetime.datetime.utcnow().isoformat(),
                "original_seed_id": node.get('_id'),
                "origin_session": session_id
            }
            meta = self.db.collection("Concepts").insert(concept_doc)
            created_concepts.append(meta)
            
            # Update Map
            seed_to_global_map[node['_id']] = meta['_id']
            
            # LINK: Seed -> Crystallized As -> Concept
            self.db.collection("Relationships").insert({
                "_from": node['_id'],
                "_to": meta['_id'],
                "type": "CRYSTALLIZED_AS",
                "session_id": session_id
            })
            
        # 2. Handle Merges
        for merge in approved_merges:
            source_id = merge['source_id'] # UserSeed
            target_id = merge['target_id'] # Existing Concept
            
            # Update Map (Merged seeds map to the EXISTING concept)
            seed_to_global_map[source_id] = target_id
            
            # create SUPPORTS/CONTRIBUTES relationship
            edge = { 
                "_from": source_id, 
                "_to": target_id, 
                "type": "CONTRIBUTES_TO", 
                "session_id": session_id,
                "confidence": merge.get('confidence', 1.0)
            }
            try:
                self.db.collection("Relationships").insert(edge)
            except:
                pass
                
            # Update Target Concept Mastery
            # Simple boost for now
            self.db.aql.execute("""
                LET doc = DOCUMENT(@target_id)
                UPDATE doc WITH { mastery: MIN([1.0, (doc.mastery || 0) + 0.05]) } IN Concepts
            """, bind_vars={"target_id": target_id})
            
        # 2.5 Migrate Internal Session Relationships
        # Now that we have the map, we act on the extracted_relation UserSeeds
        print(f"Migrating Session Edges for {session_id}...")
        aql_rels = """
        FOR doc IN UserSeeds
            FILTER doc.session_id == @session_id AND doc.type == 'extracted_relation'
            RETURN doc
        """
        session_rels = list(self.db.aql.execute(aql_rels, bind_vars={"session_id": session_id}))
        
        migrated_count = 0
        for rel in session_rels:
            # Get Global IDs
            # NOTE: session_rels use UserSeed IDs as strings in source_id/target_id fields? 
            # Check schema: In get_session_summary, we stored them as:
            # "source_id": concept_map[r['source']] -> which is a UserSeed ID
            
            src_seed_id = rel.get('source_id')
            tgt_seed_id = rel.get('target_id')
            
            global_src = seed_to_global_map.get(src_seed_id)
            global_tgt = seed_to_global_map.get(tgt_seed_id)
            
            if global_src and global_tgt:
                # Prevent Self-Loops if merged to same concept
                if global_src == global_tgt:
                    continue
                    
                # Create Global Edge
                relation_type = rel.get('relation', 'related_to').upper().replace(' ', '_')
                
                edge_doc = {
                    "_from": global_src,
                    "_to": global_tgt,
                    "type": relation_type,
                    "source": "session_crystallization",
                    "original_rel_id": rel.get('_id'),
                    "session_id": session_id,
                    "created_at": datetime.datetime.utcnow().isoformat()
                }
                self.db.collection("Relationships").insert(edge_doc)
                migrated_count += 1
                
        print(f"Migrated {migrated_count} internal edges to Global Graph.")

        # 3. Form Synapses (Auto-Association OR Manual Approval)
        if approved_synapses is not None:
             # Manual Mode
             print(f"Processing {len(approved_synapses)} User-Approved Synapses...")
             for synapse in approved_synapses:
                 # Map Source Seed -> New Concept ID
                 src_seed_id = synapse.get('source_id')
                 target_concept_id = synapse.get('target_id')
                 relation = synapse.get('relation', 'RELATED_TO')
                 
                 global_src = seed_to_global_map.get(src_seed_id)
                 
                 if global_src and target_concept_id:
                     edge = {
                        "_from": global_src,
                        "_to": target_concept_id,
                        "type": relation,
                        "source": "approved_synapse",
                        "created_at": datetime.datetime.utcnow().isoformat()
                     }
                     try:
                        self.db.collection("Relationships").insert(edge)
                     except Exception as e:
                        print(f"Failed to insert approved synapse: {e}")
        else:
            # Auto Mode (Legacy)
             await self._form_synapses(created_concepts, session_id)

        self.db.aql.execute("""
            UPDATE @key WITH { status: 'crystallized', finalized_at: DATE_ISO8601(DATE_NOW()) } IN Sessions
        """, bind_vars={"key": session_id})
        
        return {"status": "success", "message": f"Session Crystallized. {migrated_count} internal edges preserved."}


    
    async def _analyze_crystallization_batch(self, new_concepts: List[Dict], session_id: str) -> Dict[str, List[Dict]]:
        """
        Omni-Batch Analysis: Merges, Conflicts, and Synapses in ONE pass.
        Replaces legacy _form_synapses for the preview flow.
        """
        from backend.app.services.llm import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage
        import json
        
        llm = get_llm()
        print(f"[{session_id}] Omni-Batch Analysis for {len(new_concepts)} concepts...")
        
        results = {
            "synapses": [],
            "merges": [],
            "conflicts": []
        }
        
        batch_items = []

        # 1. PREPARE BATCHES (Vector Search)
        for concept in new_concepts:
            # Skip if no embedding
            if 'embedding' not in concept or not concept['embedding']:
                continue
            
            label = concept.get('label', 'Unknown')
            
            # Vector Search (Same as before)
            aql = """
            FOR doc IN Concepts
                FILTER doc._id != @concept_id
                LET score = COSINE_SIMILARITY(doc.embedding, @embedding)
                FILTER score > 0.75
                SORT score DESC
                LIMIT 8
                RETURN { label: doc.label, id: doc._id, definition: doc.definition, score: score }
            """
            
            cursor = self.db.aql.execute(aql, bind_vars={
                "concept_id": concept['_id'],
                "embedding": concept['embedding']
            })
            
            candidates = list(cursor)
            if not candidates: continue
            
            # Add to batch queue
            batch_items.append({
                "id": concept['_id'],
                "label": label,
                "definition": concept.get('definition', ''),
                "candidates": candidates
            })
            
        print(f"[{session_id}] Found {len(batch_items)} concepts with candidates.")
        
        # 2. PROCESS BATCHES (LLM)
        BATCH_SIZE = 15
        chunks = [batch_items[i:i + BATCH_SIZE] for i in range(0, len(batch_items), BATCH_SIZE)]
        
        for i, chunk in enumerate(chunks):
            print(f"[{session_id}] Processing Batch {i+1}/{len(chunks)} ({len(chunk)} items)...")
            
            # Minimize payload
            lite_chunk = []
            for item in chunk:
                lite_candidates = [{"id": c['id'], "label": c['label']} for c in item['candidates']]
                lite_chunk.append({
                    "id": item['id'],
                    "concept": item['label'],
                    "definition": item['definition'],
                    "candidates": lite_candidates
                })
            
            batch_json = json.dumps(lite_chunk)
            prompt = prompts.get("batch_crystallization_analysis", batch_json=batch_json)
            
            try:
                # Rate Limit Check
                await global_limiter.wait_for_token()
                
                response = await llm.ainvoke([
                    SystemMessage(content="You are a Knowledge Graph Architect. Output strictly JSON."),
                    HumanMessage(content=prompt)
                ])
                
                content = response.content.replace("```json", "").replace("```", "").strip()
                connections = json.loads(content)
                
                # 3. Handle Connections (Polymorphic)
                for item in connections:
                    item_type = item.get('type', '').upper()
                    source_id = item.get('source_id')
                    target_id = item.get('target_id')
                    
                    # Resolve Source Label (for logs/frontend)
                    source_item = next((x for x in chunk if x['id'] == source_id), None)
                    target_candidate = None
                    if source_item:
                         target_candidate = next((c for c in source_item['candidates'] if c['id'] == target_id), None)
                    
                    source_label = source_item['label'] if source_item else "Unknown"
                    target_label = target_candidate['label'] if target_candidate else "Unknown"

                    if item_type == "MERGE":
                        results['merges'].append({
                            "source_id": source_id,
                            "source_label": source_label,
                            "target_id": target_id,
                            "target_label": target_label,
                            "confidence": item.get('confidence', 0.9),
                            "reason": item.get('reason', 'AI proposed merge'),
                            "status": "auto_merge"
                        })
                        print(f"   -> MERGE: '{source_label}' == '{target_label}'")

                    elif item_type == "CONFLICT":
                         results['conflicts'].append({
                            "seed_text": source_label,
                            "conflicting_evidence": target_label,
                            "reason": item.get('reason', 'Logical contradiction')
                         })
                         print(f"   -> CONFLICT: '{source_label}' vs '{target_label}'")

                    elif item_type == "LINK":
                        results['synapses'].append({
                            "source_id": source_id,
                            "source_label": source_label,
                            "target_label": target_label,
                            "relation": item.get('relation', 'RELATED_TO').upper().replace(' ', '_'),
                            "confidence": "high",
                            "target_id": target_id
                        })
                        # print(f"   -> SYNAPSE: '{source_label}' -> '{target_label}'")
                            
            except Exception as e:
                print(f"   ⚠️ Omni-Batch Error: {e}")
                if "429" in str(e):
                    print("   ⚠️ Quota Exceeded. Returning partial results.")
                    break
        
        return results

    async def _form_synapses(self, new_concepts: List[Dict], session_id: str, dry_run: bool = False) -> List[Dict]:
        """ Wrapper for backward compatibility """
        # Only used by commit_crystallization for legacy auto-mode, or if someone calls it directly.
        # We can just call the new omni-batch and return the synapses part.
        results = await self._analyze_crystallization_batch(new_concepts, session_id)
        
        if not dry_run:
             # If strictly old legacy mode wanted to INSERT, we'd need to loop and insert here.
             # But 'commit_crystallization' calls this with dry_run=False? 
             # Wait, the old code INSERTED in the loop if not dry_run.
             # The new code DOES NOT INSERT. It just returns data.
             # FIX: If not dry run, we must insert the synapses.
             print(f"[{session_id}] Legacy _form_synapses called (Insert Mode). Inserting {len(results['synapses'])} synapses.")
             for syn in results['synapses']:
                 edge = {
                    "_from": syn['source_id'],
                    "_to": syn['target_id'],
                    "type": syn['relation'],
                    "source": "smart_synapse",
                    "created_at": datetime.datetime.utcnow().isoformat()
                }
                 try:
                     self.db.collection("Relationships").insert(edge)
                 except: pass
                 
        return results['synapses']

    # --- Phase 11: Graph Editing (Seeds & Edges) ---

    async def update_seed(self, session_id: str, seed_id: str, updates: Dict) -> bool:
        """
        Updates a UserSeed OR a Global Concept (if ID matches).
        """
        collection_name = "UserSeeds"
        if seed_id.startswith("Concepts/"):
            collection_name = "Concepts"

        node = self.db.collection(collection_name).get(seed_id)
        
        # Ownership check:
        # If UserSeed, must match session_id.
        # If Concept, we allow editing for now (Single User assumptions).
        if collection_name == "UserSeeds":
            if not node or node.get('session_id') != session_id:
                raise ValueError("Seed not found or does not belong to this session.")
        else:
             if not node: raise ValueError("Concept not found.")
        
        # Allowed fields
        valid_updates = {k: v for k, v in updates.items() if k in ['label', 'definition', 'type', 'name', 'text']}
        
        # Sync label/name if one changes
        if 'label' in valid_updates:
            valid_updates['name'] = valid_updates['label']
            
        update_doc = {"_key": node['_key']}
        update_doc.update(valid_updates)
        self.db.collection(collection_name).update(update_doc)
        return True

    async def delete_seed(self, session_id: str, seed_id: str, force: bool = False) -> bool:
        """
        Deletes a UserSeed and its connected edges.
        SAFETY: Checks edge count before deletion unless force=True.
        """
        seed = self.db.collection("UserSeeds").get(seed_id)
        if not seed or seed.get('session_id') != session_id:
             raise ValueError("Seed not found.")
        
        # Safety Check
        edge_query = """
        FOR e IN UserSeeds 
            FILTER (e.source_id == @id OR e.target_id == @id) AND e.type == 'extracted_relation'
            RETURN 1
        """
        edge_count = len(list(self.db.aql.execute(edge_query, bind_vars={"id": seed_id})))
        
        if edge_count > 5 and not force:
             raise ValueError(f"High-connectivity node ({edge_count} edges). Confirm deletion with force=true.")

        # Delete Edges (Cascade)
        # Filter by FULL ID (UserSeeds/key)
        self.db.aql.execute("""
            FOR doc IN UserSeeds
                FILTER (doc.source_id == @id OR doc.target_id == @id) AND doc.type == 'extracted_relation'
                REMOVE doc IN UserSeeds
        """, bind_vars={"id": seed['_id']})
        
        # Delete Node
        self.db.collection("UserSeeds").delete(seed_id)
        return True

    async def update_edge(self, session_id: str, edge_id: str, updates: Dict) -> bool:
         """ Updates a session edge (UserSeed relationship). """
         edge = self.db.collection("UserSeeds").get(edge_id)
         if not edge or edge.get('session_id') != session_id or edge.get('type') != 'extracted_relation':
              raise ValueError("Edge not found.")
              
         valid_updates = {k: v for k, v in updates.items() if k in ['relation', 'type']}
         update_doc = {"_key": edge['_key']}
         update_doc.update(valid_updates)
         self.db.collection("UserSeeds").update(update_doc)
         return True

    async def delete_edge(self, session_id: str, edge_id: str) -> bool:
         """ Deletes a session edge. """
         edge = self.db.collection("UserSeeds").get(edge_id)
         if not edge or edge.get('session_id') != session_id:
             raise ValueError("Edge not found.")
         
         self.db.collection("UserSeeds").delete(edge_id)
         return True

    async def create_edge(self, session_id: str, source_id: str, target_id: str, relation: str) -> bool:
         """ Manual creation of a session edge. """
         # Verify nodes exist
         src = self.db.collection("UserSeeds").get(source_id)
         tgt = self.db.collection("UserSeeds").get(target_id)
         
         if not src or not tgt: raise ValueError("Source or Target node not found.")
         
         edge_doc = {
             "source_id": source_id,
             "target_id": target_id,
             "relation": relation,
             "type": "extracted_relation",
             "session_id": session_id,
             "created_at": datetime.datetime.utcnow().isoformat(),
             "source": "manual_edit"
         }
         self.db.collection("UserSeeds").insert(edge_doc)
         return True

    async def generate_mermaid_diagram(self, session_id: str) -> str:
        """
        Generates a Mermaid Graph definition for the session.
        """
        # Fetch Graph Data
        summary = await self.get_session_summary(session_id)
        if not summary or 'graph_data' not in summary:
            return "graph TD;\nError[Session Not Found]"
            
        nodes = summary['graph_data']['nodes']
        links = summary['graph_data']['links']
        
        mermaid = ["graph TD"]
        
        # Style definition
        mermaid.append("    classDef evidence fill:#f96,stroke:#333,stroke-width:2px;")
        mermaid.append("    classDef thought fill:#96f,stroke:#333,stroke-width:2px;")
        mermaid.append("    classDef concept fill:#69f,stroke:#333,stroke-width:2px;")
        
        # Nodes
        for n in nodes:
            # Saniitize ID and Label
            # Mermaid IDs cannot have slashes easily, map to safe hash or replace
            safe_id = n['id'].replace('/', '_').replace('-', '_')
            safe_label = n['label'].replace('"', "'")
            
            node_class = "concept"
            if n['label'] == "Evidence": node_class = "evidence"
            if n['label'] == "Thoughs": node_class = "thought" # Typo in summary? "Thoughs" -> "Thoughts"
            
            # Use subgraph for clustering by type? No, simple graph first.
            mermaid.append(f'    {safe_id}("{safe_label}"):::{node_class}')
            
        # Links
        for l in links:
             src = l['source'].replace('/', '_').replace('-', '_')
             tgt = l['target'].replace('/', '_').replace('-', '_')
             mermaid.append(f"    {src} -->|{l['label']}| {tgt}")
             
        return "\n".join(mermaid)

    async def generate_markdown_export(self, session_id: str) -> str:
        """
        Generates a single Markdown file content with all session knowledge.
        (Obsidian compatible)
        """
        summary = await self.get_session_summary(session_id)
        if not summary: return "# Session Not Found"
        
        md = [f"# {summary['title']}"]
        md.append(f"**Goal**: {summary['goal']}")
        md.append(f"**Date**: {summary['created_at']}")
        md.append("\n---\n")
        
        md.append("## Timeline")
        for event in summary['timeline']:
            timestamp = event['timestamp'].split('T')[1][:5] # HH:MM
            icon = "📄" if event['type'] == 'evidence' else "💡"
            md.append(f"### {icon} {timestamp} - {event['type'].title()}")
            md.append(f"{event['full_content'] or event['content']}")
            if event.get('source'):
                md.append(f"*Source: {event['source']}*")
            md.append("\n")
            
        return "\n".join(md)

    async def get_node_details(self, node_id: str) -> Dict:
        """
        Fetches full details for a node, including connectivity context.
        Handles both Concepts and Seeds.
        """
        # 1. Determine Collection / Normalize ID
        collection = "Concepts"
        key = node_id
        
        if "/" in node_id:
            parts = node_id.split("/")
            collection = parts[0]
            key = parts[1]
        
        # 2. Fetch Main Document
        if not self.db.has_collection(collection):
            return None
            
        doc = self.db.collection(collection).get(key)
        if not doc:
            return None
            
        # 3. Fetch Context (Neighbors) if it's a Concept
        neighbors = []
        if collection == "Concepts":
            aql = """
            FOR v, e IN 1..1 ANY @start_node GRAPH 'concept_graph'
                RETURN {
                    node: { id: v._id, label: v.label, type: v.type },
                    edge: { type: e.type, from: e._from, to: e._to }
                }
            """
            cursor = self.db.aql.execute(aql, bind_vars={"start_node": doc["_id"]})
            neighbors = [item for item in cursor]
            
        return {
            "data": doc,
            "neighbors": neighbors,
            "type": collection
        }

    async def get_global_graph(self, limit: int = 50, offset: int = 0, session_id: str = None):
        """
        Fetches the 'Global Brain' visualization data.
        Smart Layering:
        - If session_id provided: ALWAYS returns concepts from that session (Context).
        - Then fills remainder of 'limit' with Top Global Concepts by 'val'.
        """
        aql = """
        // 1. Get Session-Specific Concepts (Priority)
        LET session_nodes = (
            FILTER @session_id != null
            FOR v, e IN 1..1 OUTBOUND CONCAT('Sessions/', @session_id) ConceptSessionLinks
                RETURN v
        )

        // 2. Get Top Global Influential Concepts
        LET global_nodes = (
            FOR doc IN Concepts
                SORT doc.val DESC
                LIMIT @offset, @limit
                RETURN doc
        )
        
        // 3. Merge and Unique
        LET all_nodes = (
            FOR n IN UNION(session_nodes, global_nodes)
                RETURN DISTINCT n
        )
        // Apply limit again to prevent explosion? No, user wants session context + global context.
        // We let session nodes exceed limit if necessary.

        LET top_ids = all_nodes[*]._id

        // 4. Get ALL relationships strictly between these nodes (Mesh)
        LET internal_edges = (
            FOR start_node IN all_nodes
                FOR v, e, p IN 1..1 ANY start_node GRAPH 'concept_graph'
                // Ensure target is also in our active list
                FILTER e._from IN top_ids AND e._to IN top_ids
                RETURN DISTINCT e
        )

        RETURN { nodes: all_nodes, links: internal_edges }
        """
        
        cursor = self.db.aql.execute(aql, bind_vars={"limit": limit, "offset": offset, "session_id": session_id})
        result = list(cursor)
        
        data = result[0] if result else {"nodes": [], "links": []}
        
        # 5. Compute Layout (Logic Crystal)
        try:
            from backend.app.services.layout_algorithms import compute_pca_layout
            # Only compute if we have nodes
            if data['nodes']:
                 layout = compute_pca_layout(data['nodes'])
                 # Enrich nodes with fixed coordinates
                 for node in data['nodes']:
                     node_id = node.get('_id')
                     if node_id in layout:
                         node['fx'] = layout[node_id]['fx']
                         node['fy'] = layout[node_id]['fy']
        except Exception as e:
            print(f"Layout Computation Failed: {e}")
            
        return data

    # ==========================================================================
    # PHASE 14: HYBRID RAG PIPELINE
    # ==========================================================================
    
    # Priority weights for different context sources
    PRIORITY_WEIGHTS = {
        "session_seeds": 1.0,      # Current session focus
        "concept_vector": 0.9,     # Crystallized knowledge
        "graph_expansion": 0.7,    # Related but indirect
        "global_seeds": 0.5,       # Fallback evidence
    }
    
    # Thresholds for pipeline decisions
    SPARSE_THRESHOLD = 2           # Triggers fallback search
    QUALITY_THRESHOLD = 0.4        # Minimum context quality score
    GAP_SCORE_THRESHOLD = 0.85     # Flags potential missed concepts
    
    # Adaptive similarity thresholds (base values)
    BASE_CONCEPT_THRESHOLD = 0.55  # More permissive to not miss existing concepts
    STRICT_CONCEPT_THRESHOLD = 0.7 # For global-only queries
    COHERENCE_THRESHOLD = 0.65     # Min score for primary concept to avoid hallucinated coherence
    
    async def search_concepts(self, query_embedding: List[float], limit: int = 5, session_id: str = None) -> List[Dict]:
        """
        Phase 14: Vector search on Concepts collection.
        Returns crystallized knowledge that matches the query.
        
        Optionally filters by session via ConceptSessionLinks.
        """
        # If session_id provided, prioritize session concepts first
        if session_id:
            aql = """
            // Session-specific concepts first
            LET session_concepts = (
                FOR link IN ConceptSessionLinks
                    FILTER link._to == CONCAT('Sessions/', @session_id)
                    LET concept = DOCUMENT(link._from)
                    FILTER concept != null AND concept.embedding != null
                    LET score = COSINE_SIMILARITY(concept.embedding, @embedding)
                    FILTER score > 0.55
                    SORT score DESC
                    LIMIT @limit
                    RETURN { concept: concept, score: score, source: 'session_concept' }
            )
            
            // Global concepts if session concepts sparse
            LET global_concepts = (
                FOR doc IN Concepts
                    FILTER doc.embedding != null
                    // Include concepts with type null, 'concept', or 'sub_concept' (exclude 'source')
                    FILTER doc.type != 'source'
                    LET score = COSINE_SIMILARITY(doc.embedding, @embedding)
                    FILTER score > 0.6
                    SORT score DESC
                    LIMIT @limit
                    RETURN { concept: doc, score: score, source: 'global_concept' }
            )
            
            // Merge - session first, then fill with global
            LET merged = UNION(session_concepts, global_concepts)
            FOR item IN merged
                COLLECT concept_id = item.concept._id INTO group
                LET best = FIRST(group[*].item)
                SORT best.score DESC
                LIMIT @limit
                RETURN best
            """
        else:
            # Global search only
            aql = """
            FOR doc IN Concepts
                FILTER doc.embedding != null
                // Include concepts with type null, 'concept', or 'sub_concept' (exclude 'source')
                FILTER doc.type != 'source'
                LET score = COSINE_SIMILARITY(doc.embedding, @embedding)
                FILTER score > 0.5
                SORT score DESC
                LIMIT @limit
                RETURN { concept: doc, score: score, source: 'global_concept' }
            """
        
        try:
            # Build bind_vars based on which branch was taken
            bind_vars = {
                "embedding": query_embedding,
                "limit": limit,
            }
            if session_id:
                bind_vars["session_id"] = session_id
            
            cursor = self.db.aql.execute(aql, bind_vars=bind_vars)
            results = list(cursor)
            print(f"[Phase 14] search_concepts: Found {len(results)} concepts")
            return results
        except Exception as e:
            print(f"[Phase 14] search_concepts error: {e}")
            return []
    
    async def expand_graph(self, concept_ids: List[str], hops: int = 1, limit: int = 10) -> List[Dict]:
        """
        Phase 14: Graph traversal from concept nodes.
        Returns related concepts within N hops with score decay.
        
        Args:
            concept_ids: Starting concept IDs for traversal
            hops: Max traversal depth (default 2 for transitive insights)
            limit: Max results to return
            
        Score decay: 1st hop = 1.0×, 2nd hop = 0.5× (prevents noise from distant nodes)
        """
        if not concept_ids:
            return []
        
        aql = """
        FOR start_id IN @concept_ids
            LET start_node = DOCUMENT(start_id)
            FILTER start_node != null
            FOR v, e, p IN 1..@hops ANY start_node GRAPH 'concept_graph'
                // Filter to only meaningful concept relationships
                FILTER v.type IN ['concept', 'sub_concept', 'source'] OR v.type == null
                // Calculate hop distance for decay
                LET hop_distance = LENGTH(p.edges)
                // Edge type weights
                LET edge_weight = (
                    e.type IN ['CAUSES', 'REQUIRES', 'ENABLES', 'HAS_PART', 'PREREQUISITE'] ? 1.0 :
                    e.type IN ['RELATED_TO', 'MENTIONS'] ? 0.6 :
                    e.type == 'CONTRADICTS' ? 0.8 :
                    0.5
                )
                // Apply hop decay: 1st hop = 1.0, 2nd hop = 0.5
                LET hop_decay = hop_distance == 1 ? 1.0 : 0.5
                LET final_weight = edge_weight * hop_decay
                
                COLLECT node_id = v._id INTO groups
                LET node = FIRST(groups[*].v)
                LET max_weight = MAX(groups[*].final_weight)
                LET edge_types = UNIQUE(groups[*].e.type)
                LET min_hops = MIN(groups[*].hop_distance)
                SORT max_weight DESC
                LIMIT @limit
                RETURN { 
                    concept: node, 
                    score: max_weight * 0.7,  // Apply graph expansion priority weight
                    edge_types: edge_types,
                    source: 'graph_expansion',
                    hops: min_hops
                }
        """
        
        try:
            cursor = self.db.aql.execute(aql, bind_vars={
                "concept_ids": concept_ids,
                "hops": hops,
                "limit": limit
            })
            results = list(cursor)
            # Flatten if nested
            if results and isinstance(results[0], list):
                results = [item for sublist in results for item in sublist]
            print(f"[Phase 14] expand_graph: Found {len(results)} related concepts from {len(concept_ids)} seeds")
            return results
        except Exception as e:
            print(f"[Phase 14] expand_graph error: {e}")
            return []
    
    async def search_global_seeds(self, query_embedding: List[float], limit: int = 5, exclude_session: str = None) -> List[Dict]:
        """
        Phase 14: Global seed search (fallback).
        Searches all Seeds without session filter.
        Optionally excludes a specific session.
        """
        aql = """
        FOR doc IN Seeds
            FILTER doc.embedding != null
            FILTER @exclude_session == null OR doc.session_id != @exclude_session
            LET score = COSINE_SIMILARITY(doc.embedding, @embedding)
            FILTER score > 0.6
            SORT score DESC
            LIMIT @limit
            RETURN { 
                seed: doc, 
                score: score * 0.5,  // Apply global seeds weight
                source: 'global_seeds' 
            }
        """
        
        try:
            cursor = self.db.aql.execute(aql, bind_vars={
                "embedding": query_embedding,
                "limit": limit,
                "exclude_session": exclude_session
            })
            results = list(cursor)
            print(f"[Phase 14] search_global_seeds: Found {len(results)} global seeds")
            return results
        except Exception as e:
            print(f"[Phase 14] search_global_seeds error: {e}")
            return []
    
    def calculate_context_quality(self, results: List[Dict]) -> float:
        """
        Phase 14: Calculate overall context quality score.
        Based on: number of results, score distribution, source diversity.
        """
        if not results:
            return 0.0
        
        # Factor 1: Number of results (more is better, up to a point)
        count_score = min(len(results) / 5, 1.0)  # Max at 5 results
        
        # Factor 2: Average score of top results
        scores = []
        for r in results:
            if 'score' in r:
                scores.append(r['score'])
            elif 'concept' in r and isinstance(r['concept'], dict):
                scores.append(r.get('score', 0))
        
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # Factor 3: Source diversity (bonus for multiple source types)
        sources = set()
        for r in results:
            sources.add(r.get('source', 'unknown'))
        diversity_bonus = min(len(sources) / 3, 0.3)  # Up to 0.3 bonus
        
        # Combined quality
        quality = (count_score * 0.3) + (avg_score * 0.5) + diversity_bonus
        
        print(f"[Phase 14] Context Quality: {quality:.3f} (count: {count_score:.2f}, avg: {avg_score:.2f}, diversity: {diversity_bonus:.2f})")
        return min(quality, 1.0)
    
    def detect_missed_concepts(self, session_seeds: List[Dict], concepts: List[Dict]) -> List[Dict]:
        """
        Phase 14: Gap Detection.
        Find high-score seeds that don't have matching concepts.
        These indicate potential knowledge that hasn't been crystallized.
        """
        missed = []
        
        # Get concept labels for comparison
        concept_labels = set()
        for c in concepts:
            if 'concept' in c and isinstance(c['concept'], dict):
                label = c['concept'].get('label', '').lower()
                if label:
                    concept_labels.add(label)
        
        for seed in session_seeds:
            score = seed.get('score', 0)
            if score >= self.GAP_SCORE_THRESHOLD:
                # High relevance seed - check if concept exists
                seed_doc = seed.get('doc', {})
                seed_text = seed_doc.get('highlight', '')[:100] if seed_doc else ''
                
                # Simple heuristic: if no concept label appears in seed, it might be a gap
                has_match = False
                for label in concept_labels:
                    if label in seed_text.lower():
                        has_match = True
                        break
                
                if not has_match and seed_text:
                    missed.append({
                        "seed_id": seed_doc.get('_id', 'unknown'),
                        "seed_text": seed_text,
                        "score": score,
                        "source": seed_doc.get('source', 'Unknown'),
                        "suggestion": "This evidence might contain concepts not yet crystallized"
                    })
        
        print(f"[Phase 14] Gap Detection: Found {len(missed)} potential missed concepts")
        return missed[:3]  # Limit to top 3 gaps
    
    async def hybrid_retrieve(self, query: str, session_id: str = None) -> Dict:
        """
        Phase 14: Orchestrator for multi-step hybrid RAG.
        
        Pipeline:
        1. Session Seeds (current session evidence)
        2a. Concept Vector Search (crystallized knowledge)
        2b. Graph Expansion (related concepts)
        3. Global Seeds Fallback (if sparse)
        4. Aggregate & Score
        
        Returns:
            {
                "results": [...],          # Combined context items
                "concepts": [...],         # Concepts found
                "seeds": [...],            # Seeds found
                "context_quality": float,  # 0-1 quality score
                "is_new_territory": bool,  # True if unknown topic
                "missed_concepts": [...],  # Gap detection flags
                "territory": "known" | "new"
            }
        """
        print(f"\n[Phase 14] ===== HYBRID RETRIEVE START =====")
        print(f"[Phase 14] Query: '{query[:50]}...' | Session: {session_id}")
        
        # Generate embedding once
        query_embedding = self.embed_query(query).tolist()
        
        all_results = []
        concepts_found = []
        seeds_found = []
        
        # ===== STEP 1: Session Seeds =====
        if session_id:
            session_seeds = await self.hybrid_search(
                query=query,
                session_id=session_id,
                intent="GENERAL",
                top_k=5,
                allow_global_fallback=False
            )
            for item in session_seeds:
                item['source'] = 'session_seeds'
                item['priority'] = self.PRIORITY_WEIGHTS['session_seeds']
            seeds_found.extend(session_seeds)
            all_results.extend(session_seeds)
            print(f"[Phase 14] Step 1 - Session Seeds: {len(session_seeds)} results")
        else:
            session_seeds = []
        
        # ===== STEP 2a: Concept Vector Search =====
        concept_results = await self.search_concepts(query_embedding, limit=5, session_id=session_id)
        for item in concept_results:
            item['priority'] = self.PRIORITY_WEIGHTS['concept_vector']
        concepts_found.extend(concept_results)
        all_results.extend(concept_results)
        print(f"[Phase 14] Step 2a - Concept Search: {len(concept_results)} results")
        
        # ===== STEP 2b: Graph Expansion =====
        if concept_results:
            concept_ids = [r['concept']['_id'] for r in concept_results if 'concept' in r and '_id' in r.get('concept', {})]
            if concept_ids:
                expanded = await self.expand_graph(concept_ids, hops=2, limit=5)  # 2-hop for transitive insights
                for item in expanded:
                    item['priority'] = self.PRIORITY_WEIGHTS['graph_expansion']
                concepts_found.extend(expanded)
                all_results.extend(expanded)
                print(f"[Phase 14] Step 2b - Graph Expansion: {len(expanded)} results")
        
        # ===== STEP 3: Global Seeds Fallback =====
        total_so_far = len(all_results)
        if total_so_far < self.SPARSE_THRESHOLD:
            print(f"[Phase 14] Step 3 - Sparse context ({total_so_far} results), triggering global fallback")
            global_seeds = await self.search_global_seeds(query_embedding, limit=5, exclude_session=session_id)
            for item in global_seeds:
                item['priority'] = self.PRIORITY_WEIGHTS['global_seeds']
            seeds_found.extend([{'doc': item.get('seed', {}), 'score': item['score'], 'source': 'global_seeds'} for item in global_seeds])
            all_results.extend(global_seeds)
            print(f"[Phase 14] Step 3 - Global Seeds: {len(global_seeds)} results")
        
        # ===== STEP 4: Aggregate & Score =====
        context_quality = self.calculate_context_quality(all_results)
        
        # ===== STEP 5: Gap Detection =====
        missed_concepts = self.detect_missed_concepts(seeds_found, concepts_found)
        
        # ===== STEP 5.5: Enhanced Territory Detection (Max Score Based) =====
        # Get max score from primary concepts (not graph expansion)
        primary_concept_scores = [r.get('score', 0) for r in concept_results if r.get('source') in ['session_concept', 'global_concept']]
        max_primary_score = max(primary_concept_scores) if primary_concept_scores else 0
        
        # Territory Thresholds:
        # - "known": At least one strong concept match (>= 0.75)
        # - "uncertain": Weak matches exist (0.5 - 0.75) - LLM evaluates relevance
        # - "new": No meaningful matches (< 0.5 or no concepts)
        
        STRONG_MATCH_THRESHOLD = 0.75  # Strong semantic match = definitely relevant
        WEAK_MATCH_THRESHOLD = 0.5     # Below this = new territory
        
        if max_primary_score >= STRONG_MATCH_THRESHOLD:
            territory = "known"
            is_new_territory = False
        elif max_primary_score >= WEAK_MATCH_THRESHOLD:
            territory = "uncertain"  # Weak matches - LLM decides relevance
            is_new_territory = False  # Not definitely new, but uncertain
        else:
            territory = "new"
            is_new_territory = True
        
        print(f"[Phase 14] Territory detection: max_score={max_primary_score:.2f} -> {territory}")
        
        print(f"[Phase 14] ===== HYBRID RETRIEVE COMPLETE =====")
        print(f"[Phase 14] Total Results: {len(all_results)} | Quality: {context_quality:.2f} | Territory: {territory}")
        print(f"[Phase 14] Concepts: {len(concepts_found)} | Seeds: {len(seeds_found)} | Gaps: {len(missed_concepts)}")
        
        # Sort by priority-weighted score
        def sort_key(item):
            base_score = item.get('score', 0)
            priority = item.get('priority', 0.5)
            return base_score * priority
        
        all_results.sort(key=sort_key, reverse=True)
        
        # ===== STEP 6: Rerank with Cross-Encoder (Phase 14 Enhancement) =====
        if self.RERANK_ENABLED and len(all_results) > 3:
            # Rerank all results using cross-encoder for better precision
            all_results = self.rerank_results(query, all_results, top_k=self.RERANK_FINAL_K)
            # Also rerank concepts separately for citations
            if concepts_found:
                concepts_found = self.rerank_results(query, concepts_found, top_k=5)
        
        return {
            "results": all_results[:10],  # Top 10 combined
            "concepts": concepts_found,
            "seeds": seeds_found,
            "context_quality": context_quality,
            "is_new_territory": is_new_territory,
            "territory": territory,
            "missed_concepts": missed_concepts
        }
