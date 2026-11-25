"""PDF 导出（经 HTML → xhtml2pdf，支持中文 UTF-8）。"""

from __future__ import annotations

import logging
import shutil
from io import BytesIO
from pathlib import Path
from typing import Optional

from oneqmultia.export.html_exporter import session_to_html
from oneqmultia.storage.models import SessionRow

_log = logging.getLogger(__name__)

# 按常见系统顺序探测。优先单文件 TTF/OTF，xhtml2pdf 对 TTC 集合支持不稳定。
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
)


def find_cjk_font() -> Optional[Path]:
    """返回第一个存在的中文字体文件。"""
    for raw in _FONT_CANDIDATES:
        path = Path(raw)
        if path.is_file():
            return _font_inside_workspace(path)
    return None


def _font_inside_workspace(font: Path) -> Path:
    """xhtml2pdf 默认只读工作目录里的文件，系统字体需要复制进来才能嵌入。"""
    root = Path.cwd().resolve()
    resolved = font.resolve()
    try:
        resolved.relative_to(root)
        return resolved
    except ValueError:
        cache = root / "data" / "fonts"
        cache.mkdir(parents=True, exist_ok=True)
        dest = cache / font.name
        if not dest.is_file() or dest.stat().st_size != font.stat().st_size:
            shutil.copy2(font, dest)
        return dest


def _inject_cjk_font(html: str, font_file: Path) -> str:
    """把字体注册进导出 HTML，让 xhtml2pdf 用它画中文。"""
    # file URI 让 ReportLab/xhtml2pdf 能读到本机字体
    src = font_file.resolve().as_uri()
    style = (
        "<style>"
        f"@font-face {{ font-family: OneQCJK; src: url('{src}'); }}"
        "body, pre, h1, h2, h3, p, code, td, th { font-family: OneQCJK, sans-serif; }"
        "</style>"
    )
    if "</head>" in html:
        return html.replace("</head>", style + "</head>", 1)
    return style + html


def session_to_pdf_bytes(session: SessionRow) -> bytes:
    """将 HTML 导出结果转为 PDF。"""
    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        raise RuntimeError("请安装 xhtml2pdf: pip install xhtml2pdf") from e

    html = session_to_html(session)
    font = find_cjk_font()
    if font is not None:
        html = _inject_cjk_font(html, font)
    else:
        _log.warning("未找到中文字体，PDF 中的中文可能显示为方框")
    out = BytesIO()
    result = pisa.CreatePDF(src=html, dest=out, encoding="utf-8")
    if getattr(result, "err", None):
        raise RuntimeError("PDF 生成失败（xhtml2pdf 报错）")
    data = out.getvalue()
    if not data:
        raise RuntimeError("PDF 生成失败（空输出）")
    return data
