"""会话全文检索。SQLite 使用 FTS5，其他数据库退回 LIKE。"""

from __future__ import annotations

from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session

from oneqmultia.storage.models import SessionRow


def search_sessions(db: Session, query: str, limit: int = 30) -> List[SessionRow]:
    """按问题、回答和最优解正文检索会话，置顶的排在前面。"""
    keyword = (query or "").strip()
    if not keyword:
        return []
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "sqlite":
        try:
            ids = _sqlite_fts_ids(db, keyword, limit)
        except Exception:
            ids = []
        if ids:
            rows = list(db.query(SessionRow).filter(SessionRow.id.in_(ids)).all())
            order = {sid: index for index, sid in enumerate(ids)}
            rows.sort(key=lambda row: (not bool(row.pinned), order.get(row.id, 999)))
            return rows
    like = f"%{keyword}%"
    rows = db.execute(
        text(
            """
            SELECT DISTINCT s.id
            FROM sessions s
            LEFT JOIN qa_pairs q ON q.session_id = s.id
            LEFT JOIN platform_answers a ON a.qa_pair_id = q.id
            WHERE s.title LIKE :q OR q.question LIKE :q OR a.answer_text LIKE :q
               OR CAST(q.optimal_answer AS TEXT) LIKE :q
            LIMIT :limit
            """
        ),
        {"q": like, "limit": limit},
    ).fetchall()
    ids = [row[0] for row in rows]
    if not ids:
        return []
    found = list(db.query(SessionRow).filter(SessionRow.id.in_(ids)).all())
    found.sort(key=lambda row: (not bool(getattr(row, "pinned", False)), row.updated_at), reverse=False)
    return found


def _sqlite_fts_ids(db: Session, keyword: str, limit: int) -> List[str]:
    """重建一份轻量 FTS 索引再查询。数据量是会话级，重建成本可接受。"""
    conn = db.connection()
    conn.exec_driver_sql(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS session_search_fts USING fts5(
            session_id UNINDEXED,
            body,
            tokenize = 'unicode61'
        )
        """
    )
    conn.exec_driver_sql("DELETE FROM session_search_fts")
    corpus = conn.exec_driver_sql(
        """
        SELECT s.id,
               COALESCE(s.title, '') || char(10) ||
               COALESCE(GROUP_CONCAT(q.question, char(10)), '') || char(10) ||
               COALESCE(GROUP_CONCAT(a.answer_text, char(10)), '') || char(10) ||
               COALESCE(GROUP_CONCAT(q.optimal_answer, char(10)), '')
        FROM sessions s
        LEFT JOIN qa_pairs q ON q.session_id = s.id
        LEFT JOIN platform_answers a ON a.qa_pair_id = q.id
        GROUP BY s.id
        """
    ).fetchall()
    for session_id, body in corpus:
        conn.exec_driver_sql(
            "INSERT INTO session_search_fts(session_id, body) VALUES (?, ?)",
            (session_id, body or ""),
        )
    # FTS5 把双引号当成短语语法，先去掉以免用户输入把查询打坏
    safe = keyword.replace('"', " ")
    matched = conn.exec_driver_sql(
        "SELECT session_id FROM session_search_fts WHERE session_search_fts MATCH ? LIMIT ?",
        (safe, limit),
    ).fetchall()
    return [row[0] for row in matched]
