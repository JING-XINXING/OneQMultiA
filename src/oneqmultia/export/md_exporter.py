"""Markdown 导出。"""

from oneqmultia.core.compare import cached_or_local_optimal
from oneqmultia.storage.models import SessionRow


def session_to_markdown(session: SessionRow) -> str:
    """会话转 Markdown（含最优解、时间与各平台回答）。"""
    lines: list[str] = []
    lines.append(f"# {session.title or 'OneQMultiA 对话'}\n")
    lines.append(f"_会话 ID: `{session.id}`_\n")
    for qa in sorted(session.qa_pairs, key=lambda q: q.created_at):
        lines.append(f"\n## 问 · {qa.question_time.isoformat()}\n")
        lines.append(qa.question.strip() + "\n")
        optimal = cached_or_local_optimal(qa)
        if optimal.get("text"):
            lines.append("\n### 最优答案\n")
            lines.append(str(optimal["text"]).strip() + "\n")
            if optimal.get("rationale"):
                lines.append(f"\n_{optimal['rationale']}_\n")
        for ans in sorted(qa.answers, key=lambda a: a.platform_id):
            lines.append(f"\n### {ans.platform_name} (`{ans.status}`)\n")
            if ans.response_duration_ms is not None:
                lines.append(f"_耗时 {ans.response_duration_ms} ms_\n")
            if ans.error_message:
                lines.append(f"> 错误: {ans.error_message}\n")
            body = (ans.answer_text or "").strip() or "_(无文本)_"
            lines.append("\n" + body + "\n")
    return "".join(lines)
