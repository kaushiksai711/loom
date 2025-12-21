from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.services.graph_rag import GraphRAGService
from backend.app.services.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

router = APIRouter()
rag_service = GraphRAGService()
llm = get_llm()

class ChatRequest(BaseModel):
    message: str
    session_id: str

@router.post("/")
async def chat_session(request: ChatRequest):
    """
    Chat with the Session Knowledge (Seeds + Ingested Docs).
    Uses Hybrid RAG.
    """
    try:
        # 1. Retrieve Context
        # Real Hybrid RAG
        context_result = await rag_service.hybrid_search(
            query=request.message, 
            session_id=request.session_id,
            top_k=5
        )
        
        # Format context (Stringify the list of documents)
        context_text = "\n".join([
            f"Result (Score: {item['score']}): {item['doc']['highlight']}" 
            for item in context_result if 'doc' in item
        ])
        
        if not context_text:
            context_text = "No direct matches found in session knowledge."
        
        # 2. Generate Answer
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
        
        return {"response": response.content}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
