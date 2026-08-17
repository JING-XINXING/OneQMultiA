"""PDF 导出（经 HTML → xhtml2pdf，支持中文 UTF-8）。"""

from __future__ import annotations

from io import BytesIO

from oneqmultia.export.html_exporter import session_to_html
from oneqmultia.storage.models import SessionRow


def session_to_pdf_bytes(session: SessionRow) -> bytes:
    """将 HTML 导出结果转为 PDF。"""
    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        raise RuntimeError("请安装 xhtml2pdf: pip install xhtml2pdf") from e

    html = session_to_html(session)
    out = BytesIO()
    # link_callback 默认即可；encoding 指定 UTF-8
    result = pisa.CreatePDF(src=html, dest=out, encoding="utf-8")
    if getattr(result, "err", None):
        raise RuntimeError("PDF 生成失败（xhtml2pdf 报错）")
    data = out.getvalue()
    if not data:
        raise RuntimeError("PDF 生成失败（空输出）")
    return data
