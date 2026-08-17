"""安装包脚本与 spec 文件存在性（不在本机跑 PyInstaller）。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_packaging_layout() -> None:
    assert (ROOT / "packaging" / "oneqmultia.spec").is_file()
    assert (ROOT / "packaging" / "windows" / "oneqmultia.iss").is_file()
    assert (ROOT / "packaging" / "windows" / "start_chrome_cdp.bat").is_file()
    assert (ROOT / "packaging" / "icons" / "generate_icons.py").is_file()
    assert (ROOT / "scripts" / "build_macos.sh").is_file()
    assert (ROOT / "scripts" / "build_windows.ps1").is_file()
    assert (ROOT / ".github" / "workflows" / "release.yml").is_file()
    spec = (ROOT / "packaging" / "oneqmultia.spec").read_text(encoding="utf-8")
    assert "desktop.py" in spec
    assert "frontend" in spec
