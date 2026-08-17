"""复用 Tab 拉回对话入口、以及原地更新回答的判定。"""

from oneqmultia.core.page_nav import is_new_answer, should_open_entry_url


def test_open_entry_when_stuck_on_site_root() -> None:
    assert should_open_entry_url("https://www.coze.cn/", "https://www.coze.cn/home")
    assert should_open_entry_url("https://www.doubao.com/", "https://www.doubao.com/chat/")
    assert should_open_entry_url("https://pi.ai/", "https://pi.ai/talk")
    assert should_open_entry_url("https://gemini.google.com/", "https://gemini.google.com/app")
    assert should_open_entry_url("https://www.lingguang.com/", "https://www.lingguang.com/chat")


def test_keep_existing_conversation_path() -> None:
    assert not should_open_entry_url("https://chatgpt.com/c/abc", "https://chatgpt.com/")
    assert not should_open_entry_url("https://gemini.google.com/app/xyz", "https://gemini.google.com/app")
    assert not should_open_entry_url("https://www.coze.cn/home", "https://www.coze.cn/home")


def test_hash_chat_entry() -> None:
    assert should_open_entry_url(
        "https://www.zidongtaichu.com/",
        "https://www.zidongtaichu.com/#/chat",
    )
    assert not should_open_entry_url(
        "https://www.zidongtaichu.com/#/chat",
        "https://www.zidongtaichu.com/#/chat",
    )


def test_in_place_answer_counts_as_new() -> None:
    assert is_new_answer(1, 1, "这是新回答内容", "欢迎使用")
    assert is_new_answer(2, 1, "第二条", "第一条")
    assert not is_new_answer(1, 1, "欢迎使用", "欢迎使用")
    assert not is_new_answer(1, 1, "", "欢迎使用")
