"""运行时路径：开发态用仓库根目录，安装包（PyInstaller）用用户数据目录。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """是否运行于 PyInstaller 打包后的可执行文件中。"""
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """只读资源根目录。

    开发：仓库根（含 pyproject.toml）。
    打包：PyInstaller 解压目录 ``sys._MEIPASS``。
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    # src/oneqmultia/paths.py → 仓库根为 parents[2]
    return here.parents[2]


def user_data_dir() -> Path:
    """用户可写数据目录（数据库、.env、日志）。可用环境变量覆盖。"""
    override = os.environ.get("ONEQMULTIA_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "OneQMultiA"
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "OneQMultiA"
    return Path.home() / ".local" / "share" / "oneqmultia"


def frontend_dist_dir() -> Path | None:
    """React 构建产物目录；不存在则返回 None。"""
    candidates = [
        resource_root() / "frontend" / "dist",
        Path(sys.executable).resolve().parent / "frontend" / "dist",
    ]
    if not is_frozen():
        candidates.append(Path.cwd() / "frontend" / "dist")
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / "index.html").is_file():
            return resolved
    return None


def env_file_candidates() -> tuple[Path, ...]:
    """``.env`` 搜索顺序：开发优先当前工作目录，安装包优先用户数据目录。"""
    cwd_env = Path.cwd() / ".env"
    user_env = user_data_dir() / ".env"
    if is_frozen():
        return (user_env, cwd_env)
    return (cwd_env, user_env)
