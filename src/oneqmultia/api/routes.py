"""问答与会话 API。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from playwright.async_api import BrowserContext
from sqlalchemy.orm import Session

from oneqmultia.api.schemas import (
    AnswerOut,
    AskBody,
    AskResponse,
    LlmChoiceBody,
    SessionCreateBody,
    SessionOut,
    SessionSummary,
)
from oneqmultia.core.aggregator import summarize_results
from oneqmultia.core.compare import answers_to_compare_payload, compare_answers
from oneqmultia.core.llm_synthesizer import llm_public_status
from oneqmultia.core.dispatcher import dispatch_to_adapters, persist_answers
from oneqmultia.core.platform_registry import PlatformRegistry
from oneqmultia.core.session_manager import (
    add_qa_pair,
    create_session,
    get_session,
    load_session_with_qa,
    is_placeholder_title,
    make_session_preview,
    maybe_update_session_title,
)
from oneqmultia.sharing.share_service import create_share_link
from oneqmultia.storage.database import get_db

router = APIRouter(tags=["qa"])


def _browser_context(request: Request) -> Optional[BrowserContext]:
    return getattr(request.app.state, "browser_context", None)


@router.post("/sessions", response_model=SessionOut)
def post_session(body: SessionCreateBody, db: Session = Depends(get_db)) -> SessionOut:
    row = create_session(db, title=body.title)
    return SessionOut.model_validate(row)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session_detail(session_id: str, db: Session = Depends(get_db)) -> SessionOut:
    row = load_session_with_qa(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionOut.model_validate(row)


@router.post("/sessions/{session_id}/ask", response_model=AskResponse)
async def post_ask(
    session_id: str,
    body: AskBody,
    request: Request,
    db: Session = Depends(get_db),
) -> AskResponse:
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")

    registry = PlatformRegistry(db)
    adapters = registry.get_enabled_adapters()
    if body.platform_ids:
        wanted = set(body.platform_ids)
        adapters = [a for a in adapters if a.platform_id in wanted]

    qa = add_qa_pair(db, session_id, body.question)
    ctx = _browser_context(request)
    results = await dispatch_to_adapters(adapters, body.question, ctx)
    rows = persist_answers(db, qa, results)
    summary = summarize_results(results)
    return AskResponse(
        qa_pair_id=qa.id,
        summary=summary,
        answers=[AnswerOut.model_validate(r) for r in rows],
    )


@router.post("/sessions/{session_id}/share")
def post_share(session_id: str, db: Session = Depends(get_db)) -> dict:
    """生成只读分享链接 token。"""
    try:
        token = create_share_link(db, session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "token": token,
        "url_path": f"/api/public/share/{token}",
    }


def _same_llm_choice(cached: dict, provider: str, model: str) -> bool:
    """缓存是否由当前所选厂商/模型生成。"""
    if not provider and not model:
        return True
    if provider and cached.get("provider") and cached.get("provider") != provider:
        return False
    if model and cached.get("model") and cached.get("model") != model:
        return False
    return True


def _build_compare(
    qa,
    db: Session,
    *,
    refresh: bool = False,
    provider: str = "",
    model: str = "",
) -> dict:
    """对比统计每次现算；最优解优先用缓存，换模型或 refresh 时重新调用 LLM。"""
    payload = answers_to_compare_payload(qa.answers)
    cached = qa.optimal_answer if isinstance(qa.optimal_answer, dict) else None
    if (
        cached
        and str(cached.get("text") or "").strip()
        and not refresh
        and _same_llm_choice(cached, provider, model)
    ):
        result = compare_answers(payload, question=qa.question, use_llm=False)
        result["optimal_answer"] = cached
        return result
    result = compare_answers(
        payload,
        question=qa.question,
        use_llm=True,
        llm_provider=provider,
        llm_model=model,
    )
    qa.optimal_answer = result.get("optimal_answer")
    db.commit()
    return result


@router.get("/llm/status")
def get_llm_status() -> dict:
    """最优答案所用大模型是否已配置（不返回 Key）。"""
    return llm_public_status()


@router.get("/sessions/{session_id}/qa/{qa_pair_id}/compare")
def get_qa_compare(
    session_id: str,
    qa_pair_id: str,
    refresh: bool = Query(False, description="为 true 时忽略缓存并重新生成最优答案"),
    provider: str = Query("", description="最优答案厂商，如 qwen / glm / minimax"),
    model: str = Query("", description="最优答案模型 id，如 qwen3.7-plus"),
    db: Session = Depends(get_db),
) -> dict:
    """获取某轮问答的答案对比与最优解。"""
    row = load_session_with_qa(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    for qa in row.qa_pairs:
        if qa.id == qa_pair_id:
            return _build_compare(qa, db, refresh=refresh, provider=provider, model=model)
    raise HTTPException(status_code=404, detail="qa_pair not found")


@router.post("/sessions/{session_id}/qa/{qa_pair_id}/compare/refresh")
def refresh_qa_compare(
    session_id: str,
    qa_pair_id: str,
    body: Optional[LlmChoiceBody] = None,
    db: Session = Depends(get_db),
) -> dict:
    """强制用指定（或当前默认）模型重写最优答案。"""
    row = load_session_with_qa(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    choice = body or LlmChoiceBody()
    for qa in row.qa_pairs:
        if qa.id == qa_pair_id:
            return _build_compare(
                qa,
                db,
                refresh=True,
                provider=choice.provider or "",
                model=choice.model or "",
            )
    raise HTTPException(status_code=404, detail="qa_pair not found")


@router.get("/sessions", response_model=List[SessionSummary])
def list_sessions(db: Session = Depends(get_db)) -> List[SessionSummary]:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from oneqmultia.storage.models import SessionRow

    stmt = (
        select(SessionRow)
        .options(selectinload(SessionRow.qa_pairs))
        .order_by(SessionRow.updated_at.desc())
    )
    rows = list(db.scalars(stmt).all())
    changed = False
    out: List[SessionSummary] = []
    for r in rows:
        qas = sorted(r.qa_pairs, key=lambda q: q.question_time)
        first_q = qas[0].question if qas else ""
        # 回填历史占位标题（如「Web 会话」），不改用户自定义标题
        if first_q and maybe_update_session_title(r, first_q):
            changed = True
        # 空的自动占位会话不进列表，避免刷屏无法区分
        if not qas and is_placeholder_title(r.title):
            continue
        out.append(
            SessionSummary(
                id=r.id,
                title=r.title,
                created_at=r.created_at,
                updated_at=r.updated_at,
                preview=make_session_preview(first_q),
                qa_count=len(qas),
            )
        )
    if changed:
        db.commit()
    return out
