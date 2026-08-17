"""智能助手服务网址校验：格式、期望域名、可选网络可达性。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_log = logging.getLogger(__name__)

# 站点存在但可能拒绝爬虫：401/403 仍视为网址有效
_REACHABLE_STATUSES = frozenset(range(200, 400)) | {401, 403, 405, 429}


@dataclass(frozen=True)
class UrlCheckResult:
    """单次网址校验结果。"""

    ok: bool
    status: str  # valid | invalid
    message: str
    final_url: str = ""
    host: str = ""


def extract_host(url: str) -> str:
    """提取去掉 www. 的小写主机名。"""
    try:
        return urlparse(url).netloc.removeprefix("www.").lower()
    except Exception:
        return ""


def hosts_match(actual_host: str, expected_host: str) -> bool:
    """判断实际主机是否等于期望域名或其子域。"""
    a = (actual_host or "").removeprefix("www.").lower()
    b = (expected_host or "").removeprefix("www.").lower()
    if not a or not b:
        return False
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def validate_url_format(url: str) -> UrlCheckResult:
    """校验 URL 语法：必须是 http(s) 且含合法主机名。"""
    raw = (url or "").strip()
    if not raw:
        return UrlCheckResult(False, "invalid", "网址为空")
    if any(ch.isspace() for ch in raw):
        return UrlCheckResult(False, "invalid", "网址不能包含空白字符")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return UrlCheckResult(False, "invalid", "网址必须以 http:// 或 https:// 开头")
    host = extract_host(raw)
    if not host or "." not in host:
        return UrlCheckResult(False, "invalid", "主机名无效，请填写完整域名")
    if parsed.username or parsed.password:
        return UrlCheckResult(False, "invalid", "网址中不要包含账号密码")
    return UrlCheckResult(True, "valid", "格式正确", final_url=raw, host=host)


def validate_expected_host(url: str, expected_host: str) -> UrlCheckResult:
    """在格式正确的前提下，核对是否仍指向该助手的期望域名。"""
    fmt = validate_url_format(url)
    if not fmt.ok:
        return fmt
    expected = (expected_host or "").strip()
    if not expected:
        return fmt
    if hosts_match(fmt.host, expected):
        return UrlCheckResult(True, "valid", f"域名匹配 {expected}", final_url=fmt.final_url, host=fmt.host)
    return UrlCheckResult(
        False,
        "invalid",
        f"当前域名 {fmt.host} 与该助手期望域名 {expected} 不符",
        final_url=fmt.final_url,
        host=fmt.host,
    )


def check_url_reachable(url: str, timeout_sec: int = 12) -> UrlCheckResult:
    """发起 HTTP 请求确认网址可访问（不要求登录）。"""
    fmt = validate_url_format(url)
    if not fmt.ok:
        return fmt
    req = Request(
        fmt.final_url,
        method="GET",
        headers={"User-Agent": "OneQMultiA-URLCheck/0.2"},
    )
    try:
        with urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310 — 已限制 http/https
            code = getattr(resp, "status", None) or resp.getcode()
            final = resp.geturl() or fmt.final_url
    except Exception as exc:
        return UrlCheckResult(False, "invalid", f"无法访问该网址：{exc}", final_url=fmt.final_url, host=fmt.host)

    final_host = extract_host(final) or fmt.host
    if int(code) not in _REACHABLE_STATUSES:
        return UrlCheckResult(
            False,
            "invalid",
            f"服务器返回 HTTP {code}，网址可能已失效",
            final_url=final,
            host=final_host,
        )
    return UrlCheckResult(True, "valid", f"可访问（HTTP {code}）", final_url=final, host=final_host)


def validate_platform_url(
    url: str,
    *,
    expected_host: str = "",
    check_network: bool = True,
) -> UrlCheckResult:
    """完整校验：格式 → 期望域名 → 可选网络探测。"""
    host_check = validate_expected_host(url, expected_host)
    if not host_check.ok:
        return host_check
    if not check_network:
        return host_check
    net = check_url_reachable(url)
    if not net.ok:
        return net
    expected = (expected_host or "").strip()
    if expected and not hosts_match(net.host, expected):
        return UrlCheckResult(
            False,
            "invalid",
            f"跳转后域名 {net.host} 与期望域名 {expected} 不符",
            final_url=net.final_url,
            host=net.host,
        )
    return net
