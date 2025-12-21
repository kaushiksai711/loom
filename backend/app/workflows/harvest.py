from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from backend.app.services.graph_rag import GraphRAGService
from backend.app.services.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
import json

class HarvestState(TypedDict):
    highlight: str
    source_url: str
    session_id: str
    context: Optional[str] # Retrieved context
    proposed_concept: Optional[dict] # LLM output
    verified_concept: Optional[dict] # User output

rag_service = GraphRAGService()
llm = get_llm()

def retrieve_context(state: HarvestState):
    """
    Step 1: Hybrid RAG
    """
    # In real impl, use rag_service.hybrid_search
    # context = rag_service.hybrid_search(state['highlight'])
    context = "Placeholder Context from Graph" 
    return {"context": context}

async def synthesize_concept(state: HarvestState):
    """
    Step 2: LLM Synthesis
    """
    prompt = f"""
    Analyze this highlight: "{state['highlight']}"
    Context: {state['context']}
    
    Extract a single Core Concept. Return JSON:
    {{
        "label": "Short Name",
        "summary": "1-sentence definition",
        "tags": ["tag1", "tag2"]
    }}
    """
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    try:
        # Basic parsing (improve with JsonOutputParser later)
        content = response.content.strip().replace("```json", "").replace("```", "")
        concept = json.loads(content)
    except:
        concept = {"label": "Parse Error", "summary": response.content}
        
    return {"proposed_concept": concept}

def crystallize(state: HarvestState):
    """
    Step 3: Save to DB (Post-Verification)
    """
    # Logic to save state['verified_concept'] to 'Concepts' collection
    print(f"Crystallizing: {state['verified_concept']}")
    return state

# Define Graph
workflow = StateGraph(HarvestState)

workflow.add_node("retrieve", retrieve_context)
workflow.add_node("synthesize", synthesize_concept)
workflow.add_node("crystallize", crystallize)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "synthesize")
# Break for human-in-the-loop
workflow.add_edge("synthesize", END) 
# Note: In a real endpoint, we'd stop here, return to UI, then resume at 'crystallize'

app = workflow.compile()
