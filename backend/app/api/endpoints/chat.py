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
    Chat with the Session Knowledge (Seeds + Ingested Docs).
    Uses Hybrid RAG.
    """
    try:
        import asyncio
        import json

        # 1. Retrieve Context (Parallel Execution)
        # Task A: Session Context (High Priority, Strict)
        # We want this to definitely finish, as it's the immediate conversation memory.
        session_task = rag_service.hybrid_search(
            query=request.message, 
            session_id=request.session_id, 
            intent=request.intent,
            top_k=5,
            allow_global_fallback=False # Strict Session Scope
        )

        # Task B: Global Scout (Background Wisdom)
        # Search everything (session_id=None) but with a strict timeout.
        global_task = rag_service.hybrid_search(
            query=request.message, 
            session_id=None, 
            intent=request.intent,
            top_k=3
        )

        # Execute
        context_result = await session_task
        
        try:
            # "Global Scout" - 800ms Timeout
            global_result = await asyncio.wait_for(global_task, timeout=0.8)
            
            # Merge & Dedup
            seen_ids = {item['doc']['_id'] for item in context_result if 'doc' in item}
            for item in global_result:
                if 'doc' in item and item['doc'].get('_id') not in seen_ids:
                    context_result.append(item)
                    print(f"[Global Scout] Found relevant insight: {item['doc'].get('label', 'Unknown')}")
                    
        except asyncio.TimeoutError:
            print("[Global Scout] Search timed out (latency protection active).")
        except Exception as e:
            print(f"[Global Scout] Failed: {e}")
        
        # Format context (Structured JSON for LLM)
        # Filter down to essential fields to save tokens
        clean_context = []
        for item in context_result:
            if 'doc' not in item: continue
            clean_context.append({
                "label": item['doc'].get('label', item['doc'].get('highlight', '')[:50]),
                "content": item['doc'].get('highlight') or item['doc'].get('text', ''),
                "source": item['doc'].get('source', 'Unknown'),
                "score": round(item['score'], 2),
                "type": item.get('edge_type', 'similarity')
            })

        context_text = json.dumps(clean_context, indent=2)
        
        if not context_result:
            context_text = "No direct matches found in knowledge base."
            
        print(f"\n[DEBUG] RAG Context ({len(context_result)} items):\n{context_text}\n")
        
        # 2. Conflict Detection (Neurosymbolic Safety Check)
        conflict_warnings = []
        try:
            # Also async this if possible, but conflict check is usually fast vector search
            conflicts = await rag_service.detect_conflicts(request.message)
            if conflicts:
                for c in conflicts:
                    conflict_warnings.append(f"[CONFLICT WARNING] Your input contradicts wisdom from '{c['seed_text'][:30]}...': {c['reason']}")
        except Exception as e:
            print(f"Conflict Check Failed: {e}")

        # 3. Generate Answer
        system_prompt = f"""You are a helpful assistant for a knowledge session. 
        Use the following context to answer the user's question. 
        If the answer is not in the context, say you don't know but offer general knowledge.
        
        Context:
        {context_text}
        """
        
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=request.message)
        ])
        
        # --- Phase 13: Log Chat Signal ---
        try:
            from backend.app.db.arango import db
            from datetime import datetime
            
            arango_db = db.get_db()
            
            # Ensure collection exists
            if not arango_db.has_collection("SessionSignals"):
                arango_db.create_collection("SessionSignals")
            
            # Extract concept labels from context for tracking
            concepts_referenced = [
                item.get("label", "Unknown")[:100] 
                for item in clean_context[:5]  # Top 5 concepts
                if item.get("label")
            ]
            
            chat_signal = {
                "session_id": request.session_id,
                "signal_type": "chat_interaction",
                "prompt": request.message[:500],  # Truncate for storage
                "prompt_length": len(request.message),
                "response_length": len(response.content),
                "concepts_referenced": concepts_referenced,
                "created_at": datetime.utcnow().isoformat()
            }
            
            arango_db.collection("SessionSignals").insert(chat_signal)
            print(f"[Analytics] Logged chat signal: {len(concepts_referenced)} concepts referenced")
            
        except Exception as log_error:
            print(f"[Analytics] Warning: Failed to log chat signal: {log_error}")
            # Don't fail the request if logging fails
        
        return {
            "response": response.content,
            "conflicts": conflict_warnings,
            "context": context_result # Return raw nodes for Graph Visualization
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
