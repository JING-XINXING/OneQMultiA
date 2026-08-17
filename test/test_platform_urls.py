"""预置平台网址：格式合法，且指向该助手期望域名。"""

from oneqmultia.platform_manager.seed import load_yaml_platforms
from oneqmultia.platform_manager.url_validator import extract_host, validate_url_format


def test_all_yaml_urls_are_https_and_well_formed() -> None:
    items = load_yaml_platforms()
    assert len(items) >= 23
    for row in items:
        url = row["url"]
        result = validate_url_format(url)
        assert result.ok, f"{row['id']} 网址无效: {url} ({result.message})"
        assert url.startswith("https://"), f"{row['id']} 必须使用 https: {url}"


def test_stepfun_uses_chat_subdomain() -> None:
    """阶跃AI 对话入口在 chat.stepfun.com，不是公司首页。"""
    items = {x["id"]: x for x in load_yaml_platforms()}
    url = items["stepfun"]["url"]
    assert extract_host(url) == "chat.stepfun.com"
    assert url.startswith("https://chat.stepfun.com/")


def test_gemini_uses_quill_editor() -> None:
    items = {x["id"]: x for x in load_yaml_platforms()}
    assert ".ql-editor" in items["gemini"]["selectors"]["input_box"]


def test_coze_uses_home_chat_entry() -> None:
    """扣子根路径常是营销页，对话入口在 /home。"""
    items = {x["id"]: x for x in load_yaml_platforms()}
    url = items["coze"]["url"]
    assert extract_host(url) == "coze.cn"
    assert "/home" in url


def test_zidongtaichu_uses_chat_hash_route() -> None:
    """紫东太初对话入口是 hash 路由 /#/chat，不是站点首页。"""
    items = {x["id"]: x for x in load_yaml_platforms()}
    url = items["zidongtaichu"]["url"]
    assert extract_host(url) == "zidongtaichu.com"
    assert url == "https://www.zidongtaichu.com/#/chat"
