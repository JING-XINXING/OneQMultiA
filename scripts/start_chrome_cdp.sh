#!/usr/bin/env bash
# 启动一个「带远程调试(CDP)的 Chrome」，供 OneQMultiA 通过 connect_over_cdp 复用你的登录态。
# 关键点：
#   - 用独立 user-data-dir，避免与日常 Chrome 抢占用户配置
#   - 端口默认 9222，与 .env 中 ONEQMULTIA_CDP_URL=http://127.0.0.1:9222 对应
#   - 首次启动后需在此窗口里逐个登录各 AI 站点（登录态会持久化到该 profile）
# 用法：
#   ./scripts/start_chrome_cdp.sh                 # 端口 9222，默认 profile 目录
#   ONEQMULTIA_CDP_PORT=9333 ./scripts/start_chrome_cdp.sh   # 自定义端口
#
# 注意：变量引用统一用 ${VAR} 花括号形式，避免变量名紧跟全角标点(如 ，) 时
#       被 bash 误并入变量名，触发 set -u 的 "unbound variable" 报错。
set -euo pipefail

PORT="${ONEQMULTIA_CDP_PORT:-9222}"
PROFILE_DIR="${ONEQMULTIA_CHROME_PROFILE:-$HOME/chrome-oneqmultia-profile}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [[ ! -x "${CHROME}" ]]; then
  echo "未找到 Chrome：${CHROME}"
  echo "如安装在别处，请修改本脚本的 CHROME 变量。"
  exit 1
fi

# 若端口已被占用，说明可能已有一个调试 Chrome 在跑
if lsof -iTCP:"${PORT}" -sTCP:LISTEN -P -n >/dev/null 2>&1; then
  echo "端口 ${PORT} 已在监听：可能已有调试版 Chrome 运行，可直接使用；或先关闭再重开。"
  exit 0
fi

mkdir -p "${PROFILE_DIR}"
echo "启动调试版 Chrome。端口=${PORT}  profile=${PROFILE_DIR}"
echo "首次使用请在弹出窗口里登录 ChatGPT / DeepSeek / Kimi 等目标站点。"
echo "请保持此 Chrome 常驻；关闭它会断开 CDP 连接。"

# 后台启动，日志丢弃
nohup "${CHROME}" \
  --remote-debugging-port="${PORT}" \
  --user-data-dir="${PROFILE_DIR}" \
  --no-first-run \
  --no-default-browser-check \
  >/dev/null 2>&1 &

echo "已启动 PID=$!  CDP 地址=http://127.0.0.1:${PORT}"
echo "接着确认 .env 中 ONEQMULTIA_CDP_URL=http://127.0.0.1:${PORT} 并重启 API。"
