"""纯文本导出。"""

from oneqmultia.export.md_exporter import session_to_markdown
from oneqmultia.storage.models import SessionRow


def session_to_txt(session: SessionRow) -> str:
    """与 Markdown 结构相同，便于纯文本阅读。"""
    return session_to_markdown(session)
