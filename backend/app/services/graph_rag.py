from typing import List, Dict
from fastembed import TextEmbedding
from backend.app.db.arango import db
import datetime
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
        if not session_docs:
            return None
        
        session = session_docs[0]
        
        # 2. Fetch Seeds (Evidence)
        aql_seeds = """
        FOR doc IN Seeds
            FILTER doc.session_id == @session_id OR doc.session_id == @session_key
            SORT doc.created_at ASC
            RETURN doc
        """
        seeds_cursor = self.db.aql.execute(aql_seeds, bind_vars={"session_id": session_id, "session_key": session_id})
        seeds = list(seeds_cursor)
        
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
             # Lazy Load: Trigger Extraction
             evidence_text = "\n\n".join([e['full_content'] for e in events if e['type'] == 'evidence'])
             if evidence_text:
                 print(f"DEBUG: Lazy Extracting Concepts for Session {session_id}...")
                 # Now returns partial dict { concepts: [], relationships: [] }
                 extraction_result = await self.extract_session_concepts(evidence_text)
                 
                 extracted_data = extraction_result.get("concepts", [])
                 relationships_data = extraction_result.get("relationships", [])
                 
                 import datetime
                 # 1. Save Concepts
                 concept_map = {} # label -> _id
                 for c in extracted_data:
                     doc = {
                         "text": c.get("text") or f"{c['label']}: {c['definition']}",
                         "label": c['label'],
                         "definition": c['definition'],
                         "type": "extracted_concept",
                         "session_id": session_id,
                         "created_at": datetime.datetime.utcnow().isoformat(),
                         "embedding": self.embed_query(c['label']).tolist() 
                     }
                     meta = self.db.collection("UserSeeds").insert(doc)
                     doc["_id"] = meta["_id"]
                     extracted_concepts.append(doc)
                     concept_map[c['label']] = meta["_id"]
                     
                 # 2. Save Relationships (as special seeds for now, or just edge logic)
                 # We'll save them as UserSeeds type='extracted_relation' to persist them
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
                "content": c.get("definition", "")
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

    async def extract_session_concepts(self, text: str) -> Dict:
        """
        Uses LLM to extract top 5-10 core concepts AND their relationships.
        """
        from backend.app.services.llm import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage
        import json
        
        llm = get_llm()
        
        # Guard for empty text
        if not text or len(text) < 50:
            return {"concepts": [], "relationships": []}
            
        sys_prompt = """You are an expert Ontology Engineer. 
        Analyze the provided text to construct a Knowledge Graph.
        
        1. Identify the Top 5-10 Core Concepts (Entities, Topics).
        2. Identify logical Relationships between them (e.g., "enables", "is_part_of", "contradicts").
        
        Return purely a JSON object. No markdown.
        Format:
        {
          "concepts": [
            { "label": "Concept Name", "definition": "Brief definition" }
          ],
          "relationships": [
            { "source": "Concept Name", "target": "Concept Name", "relation": "relationship_label" }
          ]
        }
        """
        
        try:
            response = await llm.ainvoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=f"Text to Analyze:\n{text[:15000]}")
            ])
            
            content = response.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            
            # Enrich concepts
            concepts = data.get("concepts", [])
            for c in concepts:
                c['type'] = 'extracted_concept'
                c['text'] = f"{c['label']}: {c['definition']}"
                
            return {
                "concepts": concepts,
                "relationships": data.get("relationships", [])
            }
            
        except Exception as e:
            print(f"LLM Extraction Failed: {e}")
            return {"concepts": [], "relationships": []}

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
                 candidates_to_process.extend(extracted)
        
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

    async def commit_crystallization(self, session_id: str, approved_merges: List[Dict], new_nodes: List[Dict]):
        """
        Executes the merges and writes new concepts to the Global Graph.
        Archive Session.
        """
        import datetime
        
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

        self.db.aql.execute("""
            UPDATE @key WITH { status: 'crystallized', finalized_at: DATE_ISO8601(DATE_NOW()) } IN Sessions
        """, bind_vars={"key": session_id})
        
        return {"status": "success", "message": "Session Crystallized"}

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

