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

@router.get("/{session_id}/zip")
async def export_zip(session_id: str):
    """
    Returns a ZIP archive containing:
    - session_report.md (Obsidian)
    - graph.mmd (Mermaid)
    - metadata.json (Raw Data)
    """
    try:
        import io
        import zipfile
        import json
        
        # 1. Fetch Data
        md_content = await rag_service.generate_markdown_export(session_id)
        mermaid_content = await rag_service.generate_mermaid_diagram(session_id)
        summary = await rag_service.get_session_summary(session_id)
        
        # 2. Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add Markdown
            zip_file.writestr(f"session_{session_id}.md", md_content)
            
            # Add Mermaid
            zip_file.writestr("graph.mmd", mermaid_content)
            
            # Add Metadata
            zip_file.writestr("metadata.json", json.dumps(summary, indent=2, default=str))
            
        # 3. Return Response
        zip_buffer.seek(0)
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="session_{session_id}_bundle.zip"'}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
