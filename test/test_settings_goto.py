"""导航相关配置的校验与错误文案。"""

import os

import pytest
from pydantic import ValidationError

from oneqmultia.config.settings import Settings
from oneqmultia.core.dispatcher import _format_dispatch_error


def test_goto_wait_until_invalid() -> None:
    with pytest.raises(ValidationError):
        Settings(goto_wait_until="nope")


def test_goto_timeout_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONEQMULTIA_GOTO_TIMEOUT_MS", "60000")
    s = Settings()
    assert s.goto_timeout_ms == 60000


def test_format_dispatch_timeout_message() -> None:
    class _TE(Exception):
        pass

    msg = _format_dispatch_error(_TE("Page.goto: Timeout 45000ms exceeded."))
    assert "页面打开超时" in msg
    assert "ONEQMULTIA_GOTO_TIMEOUT_MS" in msg


def test_format_dispatch_other_passthrough() -> None:
    assert _format_dispatch_error(ValueError("x")) == "x"
