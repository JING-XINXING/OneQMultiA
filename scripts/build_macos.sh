#!/usr/bin/env bash
# 在 macOS 上构建 OneQMultiA.app 与 UDZO DMG 安装包。
# 产物：release/OneQMultiA-<version>-macos.dmg
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/.venv/bin/activate"
fi

VERSION="$(python -c "import pathlib,re; t=pathlib.Path('pyproject.toml').read_text(); print(re.search(r'^version\\s*=\\s*\"([^\"]+)\"', t, re.M).group(1))")"
echo "构建 OneQMultiA ${VERSION} (macOS)"

if ! command -v npm >/dev/null 2>&1; then
  echo "需要 npm 以构建前端" >&2
  exit 1
fi

echo "==> 构建 React 前端"
(cd "$ROOT/frontend" && npm ci --ignore-scripts && npm run build)

echo "==> 生成图标"
python "$ROOT/packaging/icons/generate_icons.py"

echo "==> 安装打包依赖"
python -m pip install -q -e ".[packaging]"

echo "==> PyInstaller"
rm -rf "$ROOT/build/pyinstaller" "$ROOT/dist/OneQMultiA" "$ROOT/dist/OneQMultiA.app"
pyinstaller "$ROOT/packaging/oneqmultia.spec" \
  --noconfirm --clean \
  --distpath "$ROOT/dist" \
  --workpath "$ROOT/build/pyinstaller"

APP="$ROOT/dist/OneQMultiA.app"
if [[ ! -d "$APP" ]]; then
  echo "未生成 $APP" >&2
  exit 1
fi

echo "==> 制作 DMG"
mkdir -p "$ROOT/release" "$ROOT/build/dmg"
STAGE="$ROOT/build/dmg/OneQMultiA"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

DMG="$ROOT/release/OneQMultiA-${VERSION}-macos.dmg"
rm -f "$DMG"
hdiutil create \
  -volname "OneQMultiA" \
  -srcfolder "$STAGE" \
  -ov -format UDZO \
  "$DMG"

echo "完成：$DMG"
ls -lh "$DMG"
