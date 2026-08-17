#!/usr/bin/env bash
# OneQMultiA 一键启动：FastAPI（38421）+ 可选 Streamlit（38422）+ 可选 Vite（38423）
# 用法：
#   ./scripts/start_oneqmultia.sh              # API + Streamlit
#   ./scripts/start_oneqmultia.sh --api-only   # 仅 API
#   ./scripts/start_oneqmultia.sh --with-vite  # API + Streamlit + frontend npm dev
# 停止：Ctrl+C；或 ./scripts/stop_oneqmultia.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_DIR="$ROOT/.run"
PID_FILE="$RUN_DIR/pids"
mkdir -p "$RUN_DIR"
: >"$PID_FILE"

API_HOST="${ONEQMULTIA_API_HOST:-127.0.0.1}"
API_PORT="${ONEQMULTIA_API_PORT:-38421}"
ST_PORT="${ONEQMULTIA_STREAMLIT_PORT:-38422}"
VITE_PORT="${ONEQMULTIA_VITE_PORT:-38423}"

WITH_UI=1
WITH_VITE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-only) WITH_UI=0; shift ;;
    --with-vite) WITH_VITE=1; shift ;;
    -h|--help)
      echo "用法: $0 [--api-only] [--with-vite]"
      exit 0
      ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/.venv/bin/activate"
fi

export PYTHONPATH="${ROOT}/src:${PYTHONPATH:-}"

cleanup() {
  echo ""
  echo "正在停止服务…"
  if [[ -f "$PID_FILE" ]]; then
    while read -r pid; do
      [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    done <"$PID_FILE"
    rm -f "$PID_FILE"
  fi
  exit 0
}
trap cleanup INT TERM

echo "项目目录: $ROOT"
echo "启动 API: http://${API_HOST}:${API_PORT}  （日志: $RUN_DIR/api.log）"
nohup uvicorn oneqmultia.main:app --reload --host "$API_HOST" --port "$API_PORT" \
  >"$RUN_DIR/api.log" 2>&1 &
echo $! >>"$PID_FILE"

# 等待 API 就绪
for i in $(seq 1 60); do
  if curl -sf "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
    echo "API 已就绪。"
    break
  fi
  if [[ "$i" -eq 60 ]]; then
    echo "API 未在 60s 内就绪，请查看 $RUN_DIR/api.log"
    cleanup
    exit 1
  fi
  sleep 1
done

if [[ "$WITH_UI" -eq 1 ]]; then
  if python -m streamlit --version >/dev/null 2>&1; then
    echo "启动 Streamlit: http://${API_HOST}:${ST_PORT}  （日志: $RUN_DIR/streamlit.log）"
    nohup python -m streamlit run "$ROOT/src/oneqmultia/ui/streamlit_app.py" \
      --server.address "$API_HOST" --server.port "$ST_PORT" --browser.gatherUsageStats false \
      >"$RUN_DIR/streamlit.log" 2>&1 &
    echo $! >>"$PID_FILE"
  else
    echo "未安装 Streamlit，跳过 UI。安装: pip install -e \".[ui]\""
  fi
fi

if [[ "$WITH_VITE" -eq 1 ]]; then
  if [[ -d "$ROOT/frontend" ]] && command -v npm >/dev/null 2>&1; then
    echo "启动 Vite: http://${API_HOST}:${VITE_PORT}  （日志: $RUN_DIR/vite.log）"
    (
      cd "$ROOT/frontend"
      export ONEQMULTIA_API_PORT="$API_PORT"
      nohup npm run dev -- --port "$VITE_PORT" >"$RUN_DIR/vite.log" 2>&1 &
      echo $! >>"$PID_FILE"
    )
  else
    echo "跳过 Vite：未找到 frontend/ 或 npm。"
  fi
fi

echo ""
echo "──────── 运行中（Ctrl+C 停止）────────"
echo "  API:       http://${API_HOST}:${API_PORT}/docs"
[[ "$WITH_UI" -eq 1 ]] && echo "  Streamlit: http://${API_HOST}:${ST_PORT}/"
[[ "$WITH_VITE" -eq 1 ]] && echo "  React:     http://${API_HOST}:${VITE_PORT}/"
echo "  子进程 PID 已写入: $PID_FILE"
echo "────────────────────────────────────"
wait
