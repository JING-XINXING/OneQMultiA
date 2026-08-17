"""桌面启动入口：拉起本地 API、可选调试 Chrome，并打开浏览器界面。"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

from oneqmultia.paths import is_frozen, user_data_dir

# 与开发脚本一致，避开 3000/8000 等高频端口
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 38421
DEFAULT_CDP_PORT = 9222

_log = logging.getLogger("oneqmultia.desktop")


def _port_in_use(host: str, port: int) -> bool:
    """探测 TCP 端口是否已有进程监听。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def chrome_executable() -> Path | None:
    """定位本机 Google Chrome 可执行文件。"""
    env_path = os.environ.get("ONEQMULTIA_CHROME_PATH", "").strip()
    if env_path:
        p = Path(env_path)
        return p if p.is_file() else None
    candidates: list[Path] = []
    if sys.platform == "darwin":
        candidates.append(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    elif sys.platform == "win32":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        candidates.extend(
            [
                Path(pf) / "Google/Chrome/Application/chrome.exe",
                Path(pf86) / "Google/Chrome/Application/chrome.exe",
            ]
        )
        if local:
            candidates.append(Path(local) / "Google/Chrome/Application/chrome.exe")
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
            from shutil import which

            found = which(name)
            if found:
                return Path(found)
    for c in candidates:
        if c.is_file():
            return c
    return None


def ensure_debug_chrome(port: int = DEFAULT_CDP_PORT) -> str | None:
    """若调试端口空闲且找到 Chrome，则启动独立 profile 的 CDP 实例。

    返回将写入环境变量的 CDP URL；无法启动时返回 None。
    """
    if _port_in_use("127.0.0.1", port):
        _log.info("CDP 端口 %s 已在监听，复用现有调试 Chrome", port)
        return f"http://127.0.0.1:{port}"
    chrome = chrome_executable()
    if chrome is None:
        _log.warning("未找到 Google Chrome，跳过自动启动 CDP")
        return None
    profile = user_data_dir() / "chrome-profile"
    profile.mkdir(parents=True, exist_ok=True)
    args = [
        str(chrome),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    try:
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        _log.warning("启动调试 Chrome 失败：%s", exc)
        return None
    _log.info("已启动调试 Chrome：%s profile=%s", chrome, profile)
    return f"http://127.0.0.1:{port}"


def _ensure_user_env() -> Path:
    """确保用户数据目录与默认 .env 存在（不覆盖已有配置，避免冲掉 Key）。"""
    data = user_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    env_path = data / ".env"
    if not env_path.is_file():
        env_path.write_text(
            "ONEQMULTIA_CDP_URL=http://127.0.0.1:9222\n"
            "ONEQMULTIA_LLM_PROVIDER=auto\n",
            encoding="utf-8",
        )
    return data


def _setup_logging(data_dir: Path) -> Path:
    """窗口化安装包没有控制台，日志写入用户目录。"""
    log_file = data_dir / "oneqmultia.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr) if sys.stderr else logging.NullHandler(),
        ],
    )
    return log_file


def _redirect_stdio(log_file: Path) -> None:
    """windowed 可执行文件上 stdout/stderr 可能为 None，避免 print 崩溃。"""
    if sys.stdout is None or sys.stderr is None:
        stream = open(log_file, "a", encoding="utf-8")  # noqa: SIM115
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream


def _open_ui(url: str, delay_sec: float = 1.2) -> None:
    """稍等 API 起来后再打开系统浏览器。"""

    def _go() -> None:
        time.sleep(delay_sec)
        try:
            webbrowser.open(url)
        except Exception as exc:  # noqa: BLE001 — 打开失败不阻断服务
            _log.warning("无法打开浏览器：%s", exc)

    threading.Thread(target=_go, daemon=True, name="open-ui").start()


def _run() -> None:
    data_dir = _ensure_user_env()
    log_file = _setup_logging(data_dir)
    _redirect_stdio(log_file)

    os.environ.setdefault(
        "ONEQMULTIA_DATABASE_URL",
        f"sqlite:///{(data_dir / 'oneqmultia.db').as_posix()}",
    )
    os.environ.setdefault("ONEQMULTIA_DATA_DIR", str(data_dir))

    host = os.environ.get("ONEQMULTIA_API_HOST", DEFAULT_HOST)
    port = int(os.environ.get("ONEQMULTIA_API_PORT", str(DEFAULT_PORT)))

    if not os.environ.get("ONEQMULTIA_CDP_URL"):
        cdp = ensure_debug_chrome()
        if cdp:
            os.environ["ONEQMULTIA_CDP_URL"] = cdp

    if _port_in_use(host, port):
        _log.info("端口 %s 已占用，直接打开已有实例", port)
        webbrowser.open(f"http://{host}:{port}/")
        return

    ui_url = f"http://{host}:{port}/"
    _log.info("启动 OneQMultiA：%s （frozen=%s）", ui_url, is_frozen())
    _open_ui(ui_url)

    import uvicorn

    from oneqmultia.main import app

    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    """console_scripts / PyInstaller 入口。"""
    try:
        _run()
    except Exception:
        try:
            crash = user_data_dir() / "crash.log"
            crash.parent.mkdir(parents=True, exist_ok=True)
            crash.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        raise


if __name__ == "__main__":
    main()
