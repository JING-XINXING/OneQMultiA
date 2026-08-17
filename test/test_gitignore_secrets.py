"""确保敏感文件被 gitignore，避免把 .env / 本地数据推到远程。"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _check_ignore(rel: str) -> bool:
    r = subprocess.run(
        ["git", "check-ignore", "-q", rel],
        cwd=ROOT,
        check=False,
    )
    return r.returncode == 0


def test_gitignore_covers_secrets_and_local_state() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for token in (".env", ".venv/", "data/", "node_modules/", ".superpowers/", "release/"):
        assert token in text, f".gitignore 缺少 {token}"


def test_env_and_venv_are_ignored() -> None:
    assert _check_ignore(".env")
    assert _check_ignore(".venv/bin/python")
    assert _check_ignore("data/oneqmultia.db")
    assert _check_ignore("frontend/node_modules/react/package.json")


def test_env_example_is_not_ignored() -> None:
    r = subprocess.run(
        ["git", "check-ignore", "-q", ".env.example"],
        cwd=ROOT,
        check=False,
    )
    assert r.returncode == 1
