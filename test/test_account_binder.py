"""登录态推断（不启动浏览器）。"""

from oneqmultia.platform_manager.account_binder import infer_login_status


def test_login_page_url_is_logged_out() -> None:
    r = infer_login_status(current_url="https://chatgpt.com/auth/login")
    assert r.status == "logged_out"


def test_password_box_is_logged_out() -> None:
    r = infer_login_status(current_url="https://chat.deepseek.com/", has_password_input=True)
    assert r.status == "logged_out"


def test_input_box_is_logged_in() -> None:
    r = infer_login_status(current_url="https://chatgpt.com/", has_input_box=True)
    assert r.status == "logged_in"


def test_unknown_when_no_signals() -> None:
    r = infer_login_status(current_url="https://chatgpt.com/")
    assert r.status == "unknown"
