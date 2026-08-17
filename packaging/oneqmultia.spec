# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：onedir 打包桌面入口，并嵌入 frontend/dist 与包内 YAML。"""

from __future__ import annotations

import os
import re
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

SPECDIR = os.path.dirname(os.path.abspath(SPEC))
ROOT = os.path.abspath(os.path.join(SPECDIR, ".."))
SRC = os.path.join(ROOT, "src")

with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as _f:
    _txt = _f.read()
VERSION = re.search(r'^version\s*=\s*"([^"]+)"', _txt, re.M).group(1)

datas = [
    (os.path.join(ROOT, "frontend", "dist"), os.path.join("frontend", "dist")),
    (
        os.path.join(SRC, "oneqmultia", "config", "default_platforms.yaml"),
        os.path.join("oneqmultia", "config"),
    ),
]
binaries = []
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "oneqmultia.desktop",
    "oneqmultia.main",
    "oneqmultia.webui",
]

# Playwright CDP 驱动、导出 PDF/DOCX 依赖较散，整包收集更稳
for pkg in ("playwright", "oneqmultia"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += collect_submodules("uvicorn")
datas += collect_data_files("oneqmultia")

icon_ico = os.path.join(ROOT, "packaging", "icons", "OneQMultiA.ico")
icon_icns = os.path.join(ROOT, "packaging", "icons", "OneQMultiA.icns")
icon = icon_icns if sys.platform == "darwin" and os.path.isfile(icon_icns) else (
    icon_ico if os.path.isfile(icon_ico) else None
)

a = Analysis(
    [os.path.join(SRC, "oneqmultia", "desktop.py")],
    pathex=[SRC, ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy.tests"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OneQMultiA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OneQMultiA",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="OneQMultiA.app",
        icon=icon,
        bundle_identifier="app.oneqmultia.desktop",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "OneQMultiA",
            "CFBundleName": "OneQMultiA",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.15",
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        },
    )
