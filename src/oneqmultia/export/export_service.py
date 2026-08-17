"""统一导出入口。"""

from typing import Tuple
from urllib.parse import quote

from oneqmultia.export.docx_exporter import session_to_docx_bytes
from oneqmultia.export.html_exporter import session_to_html
from oneqmultia.export.md_exporter import session_to_markdown
from oneqmultia.export.pdf_exporter import session_to_pdf_bytes
from oneqmultia.export.txt_exporter import session_to_txt
from oneqmultia.storage.models import SessionRow

EXPORT_FORMATS = frozenset({"md", "txt", "html", "pdf", "docx"})


def _safe_filename(title: str, ext: str) -> str:
    """保留中文等 Unicode，供 RFC 5987 filename* 使用。"""
    base = "".join(c if c.isalnum() or c in "._- " else "_" for c in (title or "session")[:60]).strip()
    return f"{base or 'session'}.{ext}"


def content_disposition_attachment(filename: str) -> str:
    """
    生成可含中文的 Content-Disposition。
    Starlette 要求 header 值为 latin-1，故 ASCII 回退名 + RFC 5987 filename*。
    """
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    ascii_base = "".join(
        c if c.isascii() and (c.isalnum() or c in "._-") else "_"
        for c in filename
    ).strip("._")
    if not ascii_base or ascii_base == ext:
        ascii_base = "session"
    if not ascii_base.endswith(f".{ext}"):
        ascii_name = f"{ascii_base}.{ext}"
    else:
        ascii_name = ascii_base
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


def export_session(session: SessionRow, fmt: str) -> Tuple[bytes, str, str]:
    """
    导出会话。
    返回 (body_bytes, media_type, download_filename)。
    """
    f = fmt.lower().strip()
    if f not in EXPORT_FORMATS:
        raise ValueError(f"unsupported format: {fmt}")

    if f == "md":
        s = session_to_markdown(session)
        return (
            s.encode("utf-8"),
            "text/markdown; charset=utf-8",
            _safe_filename(session.title or "session", "md"),
        )
    if f == "txt":
        s = session_to_txt(session)
        return (
            s.encode("utf-8"),
            "text/plain; charset=utf-8",
            _safe_filename(session.title or "session", "txt"),
        )
    if f == "html":
        s = session_to_html(session)
        return (
            s.encode("utf-8"),
            "text/html; charset=utf-8",
            _safe_filename(session.title or "session", "html"),
        )
    if f == "pdf":
        b = session_to_pdf_bytes(session)
        return (b, "application/pdf", _safe_filename(session.title or "session", "pdf"))
    if f == "docx":
        b = session_to_docx_bytes(session)
        return (
            b,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            _safe_filename(session.title or "session", "docx"),
        )
    raise ValueError(f"unsupported format: {fmt}")
