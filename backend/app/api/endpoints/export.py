from fastapi import APIRouter, HTTPException, Response
from backend.app.services.graph_rag import GraphRAGService

router = APIRouter()
rag_service = GraphRAGService()

@router.get("/{session_id}/mermaid")
async def export_mermaid(session_id: str):
    """
    Returns a Mermaid JS graph definition string.
    """
    try:
        mermaid_code = await rag_service.generate_mermaid_diagram(session_id)
        return Response(content=mermaid_code, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/obsidian")
async def export_obsidian(session_id: str):
    """
    Returns a Markdown file content for Obsidian import.
    """
    try:
        markdown = await rag_service.generate_markdown_export(session_id)
        return Response(
            content=markdown, 
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="session_{session_id}.md"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
