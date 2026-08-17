"""HTML 导出（单页、UTF-8）。"""

import html as html_lib

from oneqmultia.core.compare import cached_or_local_optimal
from oneqmultia.storage.models import SessionRow


def session_to_html(session: SessionRow) -> str:
    """生成独立 HTML 页面。"""
    parts: list[str] = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'/>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'/>",
        "<title>",
        html_lib.escape(session.title or "OneQMultiA"),
        "</title><style>body{font-family:system-ui;max-width:900px;margin:24px auto;padding:0 12px;}",
        ".q{margin:24px 0;padding:12px;background:#f5f5f5;border-radius:8px;}",
        ".a{margin:8px 0;padding:12px;border:1px solid #ddd;border-radius:8px;}",
        ".opt{margin:12px 0;padding:16px;border:1px solid #f3d19e;background:#fffbeb;border-radius:12px;}",
        "pre{white-space:pre-wrap;word-break:break-word;}</style></head><body>",
        "<h1>",
        html_lib.escape(session.title or "对话导出"),
        "</h1>",
        f"<p>会话 ID: <code>{html_lib.escape(session.id)}</code></p>",
    ]
    for qa in sorted(session.qa_pairs, key=lambda q: q.created_at):
        parts.append("<div class='q'><h2>问题</h2>")
        parts.append(f"<p><small>{html_lib.escape(qa.question_time.isoformat())}</small></p>")
        parts.append(f"<pre>{html_lib.escape(qa.question)}</pre></div>")
        optimal = cached_or_local_optimal(qa)
        if optimal.get("text"):
            parts.append("<div class='opt'><h2>最优答案</h2>")
            parts.append(f"<pre>{html_lib.escape(str(optimal['text']))}</pre>")
            if optimal.get("rationale"):
                parts.append(f"<p><small>{html_lib.escape(str(optimal['rationale']))}</small></p>")
            parts.append("</div>")
        for ans in sorted(qa.answers, key=lambda a: a.platform_id):
            parts.append("<div class='a'>")
            parts.append(f"<h3>{html_lib.escape(ans.platform_name)} — {html_lib.escape(ans.status)}</h3>")
            if ans.response_duration_ms is not None:
                parts.append(f"<p><small>{ans.response_duration_ms} ms</small></p>")
            if ans.error_message:
                parts.append(f"<p style='color:red'>{html_lib.escape(ans.error_message)}</p>")
            parts.append(f"<pre>{html_lib.escape(ans.answer_text or '')}</pre></div>")
    parts.append("</body></html>")
    return "".join(parts)
