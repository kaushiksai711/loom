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
        # 1. Retrieve Context
        # Real Hybrid RAG
        # User requested "World Knowledge" access for Neuro Chat, so we pass session_id=None to search GLOBAL seeds.
        context_result = await rag_service.hybrid_search(
            query=request.message, 
            session_id=request.session_id, # ENABLE SESSION SCOPE
            intent=request.intent,
            top_k=5
        )
        
        # Format context (Stringify the list of documents)
        context_text = "\n".join([
            f"Result (Score: {item['score']:.2f}):\n"
            f"  Highlight: {item['doc'].get('highlight', item['doc'].get('label', 'Unknown'))}\n"
            f"  Context: {item['doc'].get('context', 'No surrounding context available.')}\n"
            for item in context_result if 'doc' in item
        ])
        
        if not context_text:
            context_text = "No direct matches found in global knowledge."
            
        print(f"\n[DEBUG] RAG Context ({len(context_result)} items):\n{context_text}\n")
        
        # 2. Conflict Detection (Neurosymbolic Safety Check)
        conflict_warnings = []
        try:
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
        
        return {
            "response": response.content,
            "conflicts": conflict_warnings,
            "context": context_result # Return raw nodes for Graph Visualization
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
