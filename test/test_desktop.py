"""桌面启动器：端口探测与 Chrome 路径（不真正拉起浏览器）。"""

from __future__ import annotations

from pathlib import Path

from oneqmultia import desktop


def test_port_in_use_false_on_closed_port() -> None:
    assert desktop._port_in_use("127.0.0.1", 59999) is False


def test_chrome_executable_env_override(tmp_path: Path, monkeypatch) -> None:
    fake = tmp_path / "chrome"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setenv("ONEQMULTIA_CHROME_PATH", str(fake))
    assert desktop.chrome_executable() == fake


def test_chrome_executable_missing_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ONEQMULTIA_CHROME_PATH", str(tmp_path / "missing-chrome"))
    assert desktop.chrome_executable() is None


def test_ensure_debug_chrome_reuses_open_port(monkeypatch) -> None:
    monkeypatch.setattr(desktop, "_port_in_use", lambda host, port: True)
    url = desktop.ensure_debug_chrome(9222)
    assert url == "http://127.0.0.1:9222"


def test_ensure_user_env_writes_once(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ONEQMULTIA_DATA_DIR", str(tmp_path))
    data = desktop._ensure_user_env()
    env_path = data / ".env"
    assert env_path.is_file()
    original = env_path.read_text(encoding="utf-8")
    env_path.write_text("ONEQMULTIA_CDP_URL=keep-me\n", encoding="utf-8")
    desktop._ensure_user_env()
    assert "keep-me" in env_path.read_text(encoding="utf-8")
    assert original  # 首次写入非空
