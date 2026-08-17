# Windows 安装包构建（在 Windows 或 GitHub Actions windows-latest 上运行）
# 产物：release/OneQMultiA-<version>-win64-setup.exe
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$pyproject = Get-Content -Raw "pyproject.toml"
if ($pyproject -notmatch 'version\s*=\s*"([^"]+)"') {
    throw "无法从 pyproject.toml 读取 version"
}
$Version = $Matches[1]
Write-Host "构建 OneQMultiA $Version (Windows)"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "需要 npm 以构建前端"
}

Write-Host "==> 构建 React 前端"
Push-Location "$Root\frontend"
npm ci --ignore-scripts
npm run build
Pop-Location

Write-Host "==> 生成图标"
python "$Root\packaging\icons\generate_icons.py"

Write-Host "==> 安装打包依赖"
python -m pip install -q -e ".[packaging]"

Write-Host "==> PyInstaller"
if (Test-Path "$Root\dist\OneQMultiA") { Remove-Item -Recurse -Force "$Root\dist\OneQMultiA" }
python -m PyInstaller "$Root\packaging\oneqmultia.spec" --noconfirm --clean --distpath "$Root\dist" --workpath "$Root\build\pyinstaller"

$exeDir = Join-Path $Root "dist\OneQMultiA"
if (-not (Test-Path (Join-Path $exeDir "OneQMultiA.exe"))) {
    throw "未生成 dist\OneQMultiA\OneQMultiA.exe"
}

Copy-Item "$Root\packaging\windows\start_chrome_cdp.bat" -Destination $exeDir -Force

New-Item -ItemType Directory -Force -Path "$Root\release" | Out-Null

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Write-Host "未找到 Inno Setup，输出便携目录 dist\OneQMultiA （可手动压缩为 zip）"
    $zip = Join-Path $Root "release\OneQMultiA-$Version-win64-portable.zip"
    if (Test-Path $zip) { Remove-Item $zip }
    Compress-Archive -Path "$exeDir\*" -DestinationPath $zip
    Write-Host "完成：$zip"
    exit 0
}

Write-Host "==> Inno Setup"
& $iscc /DRepoRoot="$Root" /DMyAppVersion="$Version" "$Root\packaging\windows\oneqmultia.iss"
Write-Host "完成：release\OneQMultiA-$Version-win64-setup.exe"
