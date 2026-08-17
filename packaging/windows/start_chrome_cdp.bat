@echo off
REM 启动带远程调试端口的 Chrome，供 OneQMultiA 通过 CDP 复用登录态。
REM 使用独立 user-data-dir，不影响日常 Chrome 配置。
setlocal
set "PORT=%ONEQMULTIA_CDP_PORT%"
if "%PORT%"=="" set "PORT=9222"
set "PROFILE=%ONEQMULTIA_CHROME_PROFILE%"
if "%PROFILE%"=="" set "PROFILE=%LOCALAPPDATA%\OneQMultiA\chrome-profile"

set "CHROME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

if "%CHROME%"=="" (
  echo 未找到 Google Chrome，请安装后再运行。
  exit /b 1
)

if not exist "%PROFILE%" mkdir "%PROFILE%"
echo 启动调试版 Chrome  端口=%PORT%  profile=%PROFILE%
start "" "%CHROME%" --remote-debugging-port=%PORT% --user-data-dir="%PROFILE%" --no-first-run --no-default-browser-check
echo CDP 地址: http://127.0.0.1:%PORT%
echo 请在弹出的窗口中登录各 AI 站点，并保持该 Chrome 常驻。
endlocal
