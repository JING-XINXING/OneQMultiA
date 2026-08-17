"""Word (.docx) 导出。"""

from io import BytesIO

from docx import Document
from docx.shared import Pt

from oneqmultia.core.compare import cached_or_local_optimal
from oneqmultia.storage.models import SessionRow


def session_to_docx_bytes(session: SessionRow) -> bytes:
    """生成 docx 二进制。"""
    doc = Document()
    t = doc.add_heading(session.title or "OneQMultiA 对话", level=0)
    t.runs[0].font.size = Pt(18)
    doc.add_paragraph(f"会话 ID: {session.id}")

    for qa in sorted(session.qa_pairs, key=lambda q: q.created_at):
        doc.add_heading("问题", level=1)
        doc.add_paragraph(qa.question_time.isoformat())
        doc.add_paragraph(qa.question)
        optimal = cached_or_local_optimal(qa)
        if optimal.get("text"):
            doc.add_heading("最优答案", level=2)
            doc.add_paragraph(str(optimal["text"]))
            if optimal.get("rationale"):
                doc.add_paragraph(str(optimal["rationale"]))
        for ans in sorted(qa.answers, key=lambda a: a.platform_id):
            doc.add_heading(f"{ans.platform_name} ({ans.status})", level=2)
            if ans.response_duration_ms is not None:
                doc.add_paragraph(f"耗时: {ans.response_duration_ms} ms")
            if ans.error_message:
                doc.add_paragraph(f"错误: {ans.error_message}")
            doc.add_paragraph(ans.answer_text or "")

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
