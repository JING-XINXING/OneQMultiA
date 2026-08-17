"""公开只读接口（分享链接）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from oneqmultia.api.schemas import SessionOut
from oneqmultia.sharing.share_service import resolve_shared_session
from oneqmultia.storage.database import get_db

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/share/{token}", response_model=SessionOut)
def get_shared_session(token: str, db: Session = Depends(get_db)) -> SessionOut:
    """通过分享 token 只读查看整段会话。"""
    row = resolve_shared_session(db, token)
    if row is None:
        raise HTTPException(status_code=404, detail="分享不存在或已失效")
    return SessionOut.model_validate(row)
