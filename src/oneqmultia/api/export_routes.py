"""导出下载 API。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from oneqmultia.core.session_manager import load_session_with_qa
from oneqmultia.export.export_service import (
    EXPORT_FORMATS,
    content_disposition_attachment,
    export_session,
)
from oneqmultia.storage.database import get_db

router = APIRouter(tags=["export"])


@router.get("/sessions/{session_id}/export")
def download_export(
    session_id: str,
    format: str = Query(..., description="md | txt | html | pdf | docx"),
    db: Session = Depends(get_db),
) -> Response:
    """下载会话为指定格式文件。"""
    row = load_session_with_qa(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        body, media_type, filename = export_session(row, format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": content_disposition_attachment(filename),
        },
    )


@router.get("/export/formats")
def list_export_formats() -> dict:
    """列出支持的导出格式。"""
    return {"formats": sorted(EXPORT_FORMATS)}
