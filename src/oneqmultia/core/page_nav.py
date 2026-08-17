"""复用 Chrome Tab 时判断是否要拉回配置的对话入口。"""

from urllib.parse import urlparse


def should_open_entry_url(current_url: str, entry_url: str) -> bool:
    """
    复用同域 Tab 时：若当前停在站点根路径，而配置入口是 /chat、/home、/#/chat 等，
    则应导航到入口，否则首页没有提问框。
    已在对话子路径（如 /c/xxx、/app/yyy）时不打断。
    """
    if not current_url or not entry_url:
        return False
    try:
        current = urlparse(current_url)
        entry = urlparse(entry_url)
    except Exception:
        return False

    curr_path = (current.path or "/").rstrip("/") or "/"
    entry_path = (entry.path or "/").rstrip("/") or "/"
    entry_hash = (entry.fragment or "").strip()
    curr_hash = (current.fragment or "").strip()

    if entry_path != "/" and curr_path == "/":
        return True
    if entry_hash and entry_hash != curr_hash and curr_path == entry_path:
        return True
    return False


def is_new_answer(curr_count: int, pre_count: int, text: str, pre_last_text: str) -> bool:
    """
    新回答判定：节点变多，或最后一条文本相对发送前发生变化。
    豆包/Pi/灵光等常原地改最后一条，只数节点会空等到超时。
    """
    body = (text or "").strip()
    if not body:
        return False
    if curr_count > pre_count:
        return True
    return body != (pre_last_text or "").strip()
