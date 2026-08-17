"""刷新恢复会话：与 frontend/src/lib/sessionPersist.ts 的选择规则保持一致。"""

from typing import Optional


def resolve_session_to_restore(
    stored_id: Optional[str],
    sessions: list[dict],
) -> Optional[str]:
    """优先上次会话；空占位或不存在时回退到最近有问答的会话。"""
    if stored_id:
        stored = next((item for item in sessions if item["id"] == stored_id), None)
        if stored and (stored.get("qa_count") or 0) > 0:
            return stored["id"]
    with_qa = next((item for item in sessions if (item.get("qa_count") or 0) > 0), None)
    return with_qa["id"] if with_qa else None


def test_restore_keeps_last_session_with_answers() -> None:
    sessions = [
        {"id": "old", "qa_count": 2},
        {"id": "current", "qa_count": 1},
    ]
    assert resolve_session_to_restore("current", sessions) == "current"


def test_restore_skips_empty_placeholder() -> None:
    sessions = [
        {"id": "has-qa", "qa_count": 3},
        {"id": "empty", "qa_count": 0},
    ]
    assert resolve_session_to_restore("empty", sessions) == "has-qa"


def test_restore_missing_stored_id_uses_latest_with_qa() -> None:
    sessions = [
        {"id": "latest", "qa_count": 1},
        {"id": "older", "qa_count": 4},
    ]
    assert resolve_session_to_restore("deleted", sessions) == "latest"
    assert resolve_session_to_restore(None, sessions) == "latest"


def test_restore_no_sessions_stays_blank() -> None:
    assert resolve_session_to_restore("any", []) is None
    assert resolve_session_to_restore(None, [{"id": "empty", "qa_count": 0}]) is None
