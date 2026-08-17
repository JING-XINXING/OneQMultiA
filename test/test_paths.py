"""路径解析与用户数据目录。"""

from __future__ import annotations

from pathlib import Path

from oneqmultia.paths import env_file_candidates, frontend_dist_dir, is_frozen, resource_root, user_data_dir


def test_not_frozen_in_pytest() -> None:
    assert is_frozen() is False


def test_resource_root_is_repo(tmp_path: Path) -> None:
    root = resource_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "oneqmultia").is_dir()


def test_user_data_dir_env_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ONEQMULTIA_DATA_DIR", str(tmp_path / "custom-data"))
    assert user_data_dir() == (tmp_path / "custom-data").resolve()


def test_env_file_candidates_include_cwd(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ONEQMULTIA_DATA_DIR", str(tmp_path / "ud"))
    names = {p.name for p in env_file_candidates()}
    assert names == {".env"}
    assert (tmp_path / ".env") in env_file_candidates()


def test_frontend_dist_dir_none_without_index(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    # 仓库里可能已有 frontend/dist；本测试只断言函数返回 Path 或 None，且若有则含 index.html
    found = frontend_dist_dir()
    if found is not None:
        assert (found / "index.html").is_file()
