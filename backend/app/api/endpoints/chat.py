from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.services.graph_rag import GraphRAGService
from backend.app.services.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

router = APIRouter()
rag_service = GraphRAGService()
llm = get_llm()

from enum import Enum

class ChatIntent(str, Enum):
    GENERAL = "GENERAL"
    FACT_CHECK = "FACT_CHECK"
    LEARNING = "LEARNING"

class ChatRequest(BaseModel):
    message: str
    session_id: str
    intent: ChatIntent = ChatIntent.GENERAL

@router.post("")
async def chat_session(request: ChatRequest):
    """
    Phase 14: Chat with Hybrid RAG.
    Uses multi-step retrieval: Session Seeds -> Concepts -> Graph Expansion -> Global Fallback.
    """
    try:
        import asyncio
        import json

        # ===== PHASE 14: Use Hybrid Retrieve =====
        rag_result = await rag_service.hybrid_retrieve(
            query=request.message,
            session_id=request.session_id
        )
        
        # Extract components from hybrid result
        all_results = rag_result.get("results", [])
        concepts_found = rag_result.get("concepts", [])
        seeds_found = rag_result.get("seeds", [])
        context_quality = rag_result.get("context_quality", 0)
        is_new_territory = rag_result.get("is_new_territory", False)
        territory = rag_result.get("territory", "known")
        missed_concepts = rag_result.get("missed_concepts", [])
        
        # ===== Format Context for LLM =====
        # Include both Concepts (crystallized knowledge) and Seeds (raw evidence)
        clean_context = []
        concept_citations = []
        seed_citations = []
        
        # Process Concepts
        for item in concepts_found:
            concept = item.get('concept', {})
            if not concept:
                continue
            label = concept.get('label', concept.get('name', 'Unknown'))
            definition = concept.get('definition', '')
            concept_id = concept.get('_id', 'unknown')
            score = item.get('score', 0)
            source_type = item.get('source', 'concept')
            
            clean_context.append({
                "type": "concept",
                "label": label,
                "definition": definition[:500] if definition else "",
                "id": concept_id,
                "score": round(score, 2),
                "source_type": source_type
            })
            
            concept_citations.append({
                "id": concept_id,
                "label": label,
                "type": source_type
            })
        
        # Process Seeds (Evidence)
        for item in seeds_found[:5]:  # Limit seeds in context
            doc = item.get('doc', {})
            if not doc:
                continue
            highlight = doc.get('highlight', doc.get('text', ''))
            source = doc.get('source', 'Unknown')
            seed_id = doc.get('_id', 'unknown')
            score = item.get('score', 0)
            
            clean_context.append({
                "type": "evidence",
                "content": highlight[:400] if highlight else "",
                "source": source,
                "id": seed_id,
                "score": round(score, 2),
                "source_type": item.get('source', 'seed')
            })
            
            # Only add meaningful citations
            if highlight and len(highlight) > 20:
                seed_citations.append({
                    "id": seed_id,
                    "label": highlight[:50] + "..." if len(highlight) > 50 else highlight,
                    "source": source
                })
        
        context_text = json.dumps(clean_context, indent=2)
        
        print(f"\n[DEBUG] Hybrid RAG Context ({len(clean_context)} items, Quality: {context_quality:.2f}):\n{context_text[:1000]}...\n")
        
        # ===== Handle Response Modes (3 territories: known, uncertain, new) =====
        if territory == "new":
            # Mode C: New Territory - No meaningful matches
            system_prompt = f"""You are a helpful knowledge assistant. 
This topic is NOT in the user's knowledge base. No relevant concepts were found.

INSTRUCTIONS:
1. Clearly state: "This topic is not yet in your knowledge base."
2. Provide general knowledge from your training, clearly labeled as such.
3. Suggest starting a "Learning Session" on this topic.
"""
        elif territory == "uncertain":
            # Mode B: Uncertain Territory - Weak matches that may or may not be relevant
            system_prompt = f"""You are a helpful knowledge assistant.
The following context was found but may not be directly relevant to the question.
Max relevance score: {context_quality:.2f} (weak match)

Available Context:
{context_text if clean_context else "No context available."}

CRITICAL INSTRUCTIONS:
1. FIRST, evaluate if the provided context ACTUALLY addresses the user's specific question.
2. IF CONTEXT IS NOT RELEVANT to the question asked:
   - Say clearly: "This topic is not yet in your knowledge base."
   - Provide general knowledge from your training
   - Suggest a "Learning Session" for this topic
3. IF CONTEXT IS RELEVANT (even partially):
   - Use it to inform your answer
   - Acknowledge what's covered and what isn't

You have FULL AUTHORITY to ignore irrelevant context. Don't force-fit weak matches.
"""
        else:
            # Mode A: Known Territory - Strong concept match found
            system_prompt = f"""You are a helpful knowledge assistant for a learning session. 
Strong concept matches were found in the knowledge base.

Context:
{context_text}

INSTRUCTIONS:
1. Use the provided context to answer the question
2. Prioritize Concepts (verified knowledge) over raw Evidence
3. Reference sources naturally (e.g., "Based on your knowledge of X...")
4. If partially relevant, acknowledge what's covered and what isn't
"""
        
        # ===== Conflict Detection =====
        conflict_warnings = []
        try:
            conflicts = await rag_service.detect_conflicts(request.message)
            if conflicts:
                for c in conflicts:
                    conflict_warnings.append(f"[CONFLICT WARNING] Your input contradicts wisdom from '{c['seed_text'][:30]}...': {c['reason']}")
        except Exception as e:
            print(f"Conflict Check Failed: {e}")

        # ===== Generate Answer =====
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=request.message)
        ])
        
        # ===== Phase 13: Log Chat Signal =====
        try:
            from backend.app.db.arango import db
            from datetime import datetime
            
            arango_db = db.get_db()
            
            if not arango_db.has_collection("SessionSignals"):
                arango_db.create_collection("SessionSignals")
            
            concepts_referenced = [
                c.get("label", "Unknown")[:100] 
                for c in concept_citations[:5]
            ]
            
            chat_signal = {
                "session_id": request.session_id,
                "signal_type": "chat_interaction",
                "prompt": request.message[:500],
                "prompt_length": len(request.message),
                "response_length": len(response.content),
                "concepts_referenced": concepts_referenced,
                "territory": territory,
                "context_quality": context_quality,
                "created_at": datetime.utcnow().isoformat()
            }
            
            arango_db.collection("SessionSignals").insert(chat_signal)
            print(f"[Analytics] Logged chat signal: {len(concepts_referenced)} concepts, territory={territory}")
            
        except Exception as log_error:
            print(f"[Analytics] Warning: Failed to log chat signal: {log_error}")
        
        # ===== Build Response with Phase 14 Metadata =====
        return {
            "response": response.content,
            "conflicts": conflict_warnings,
            "context": all_results,  # Full hybrid results
            
            # Phase 14: New metadata fields
            "grounded": not is_new_territory,
            "territory": territory,
            "context_quality": round(context_quality, 2),
            "missed_concepts": missed_concepts,
            
            # Structured citations
            "citations": {
                "concepts": concept_citations[:5],
                "evidence": seed_citations[:5]
            }
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
