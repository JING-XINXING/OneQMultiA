"""网址格式与期望域名校验（不访问网络）。"""

from oneqmultia.platform_manager.url_validator import (
    extract_host,
    hosts_match,
    validate_expected_host,
    validate_url_format,
)


def test_valid_https_url() -> None:
    r = validate_url_format("https://chatgpt.com/")
    assert r.ok
    assert r.host == "chatgpt.com"


def test_reject_empty_and_javascript() -> None:
    assert not validate_url_format("").ok
    assert not validate_url_format("javascript:alert(1)").ok
    assert not validate_url_format("ftp://chatgpt.com").ok
    assert not validate_url_format("https://chatgpt.com/path with space").ok


def test_reject_embedded_credentials() -> None:
    assert not validate_url_format("https://user:pass@chatgpt.com/").ok


def test_expected_host_match_and_mismatch() -> None:
    ok = validate_expected_host("https://chat.deepseek.com/", "deepseek.com")
    assert ok.ok
    bad = validate_expected_host("https://evil.example/", "chatgpt.com")
    assert not bad.ok
    assert "不符" in bad.message


def test_hosts_match_subdomain() -> None:
    assert hosts_match("chat.qwen.ai", "qwen.ai")
    assert extract_host("https://www.kimi.com/chat") == "kimi.com"
