"""非回环绑定时保护会改数据或消耗额度的接口。"""

from __future__ import annotations

from oneqmultia.config.settings import Settings

# 这些写操作在远程监听时必须带访问令牌
_PROTECTED_PREFIXES = (
    "/api/platforms",
    "/api/sessions",
)


def bind_requires_token(api_host: str) -> bool:
    """只有监听非本机地址时才要求令牌。本机 127.0.0.1 保持免密。"""
    host = (api_host or "").strip().lower()
    return host not in {"", "127.0.0.1", "localhost", "::1"}


def request_is_allowed(method: str, path: str, authorization: str, settings: Settings) -> bool:
    """GET 公开读和分享页放行；远程写操作核对 Bearer token。"""
    if not bind_requires_token(settings.api_host):
        return True
    if path.startswith("/api/public") or path in {"/health", "/docs", "/openapi.json", "/redoc"}:
        return True
    if method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return True
    if not any(path.startswith(prefix) for prefix in _PROTECTED_PREFIXES):
        return True
    expected = (settings.access_token or "").strip()
    if not expected:
        return False
    return authorization.strip() == f"Bearer {expected}"
