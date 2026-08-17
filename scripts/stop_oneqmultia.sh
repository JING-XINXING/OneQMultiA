#!/usr/bin/env bash
# OneQMultiA 一键停止：结束 start_oneqmultia.sh 写入 .run/pids 的进程；可选按端口释放。
# 用法：
#   ./scripts/stop_oneqmultia.sh              # 读 .run/pids，SIGTERM
#   ./scripts/stop_oneqmultia.sh --force      # TERM 后再 KILL 仍监听的端口 + 匹配进程名
#   ./scripts/stop_oneqmultia.sh --ports      # 无 pids 或需兜底：lsof 释放 38421/38422/38423
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/.run"
PID_FILE="$RUN_DIR/pids"

API_PORT="${ONEQMULTIA_API_PORT:-38421}"
ST_PORT="${ONEQMULTIA_STREAMLIT_PORT:-38422}"
VITE_PORT="${ONEQMULTIA_VITE_PORT:-38423}"

FORCE=0
USE_PORTS=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --ports) USE_PORTS=1; shift ;;
    -h|--help)
      echo "用法: $0 [--force] [--ports]"
      echo "  --force  第二轮对残留端口 / 匹配进程使用 SIGKILL"
      echo "  --ports  用 lsof 结束占用 ${API_PORT} ${ST_PORT} ${VITE_PORT} 的进程"
      exit 0
      ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

_kill_tree() {
  local pid="$1"
  [[ -z "$pid" ]] && return 0
  if command -v pgrep >/dev/null 2>&1; then
    local c
    c=$(pgrep -P "$pid" 2>/dev/null || true)
    for child in $c; do
      _kill_tree "$child"
    done
  fi
  kill -TERM "$pid" 2>/dev/null || true
}

_kill_port_term() {
  local port="$1"
  local pids
  pids=$(lsof -ti ":$port" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    echo "释放端口 $port → $pids"
    for p in $pids; do
      kill -TERM "$p" 2>/dev/null || true
    done
  fi
}

_kill_port_kill() {
  local port="$1"
  local pids
  pids=$(lsof -ti ":$port" 2>/dev/null || true)
  for p in $pids; do
    kill -KILL "$p" 2>/dev/null || true
  done
}

n=0
if [[ -f "$PID_FILE" ]]; then
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    if kill -0 "$pid" 2>/dev/null; then
      echo "停止 PID $pid …"
      _kill_tree "$pid"
      n=$((n + 1))
    fi
  done <"$PID_FILE"
  rm -f "$PID_FILE"
fi

if [[ "$n" -eq 0 ]]; then
  echo "未找到 .run/pids 或进程已退出。"
fi

if [[ "$USE_PORTS" -eq 1 ]] && command -v lsof >/dev/null 2>&1; then
  _kill_port_term "$API_PORT"
  _kill_port_term "$ST_PORT"
  _kill_port_term "$VITE_PORT"
fi

if [[ "$FORCE" -eq 1 ]]; then
  sleep 1
  # 按命令行匹配本项目（降低误杀其他 uvicorn/streamlit）
  if command -v pgrep >/dev/null 2>&1; then
    for p in $(pgrep -f "uvicorn.*oneqmultia\.main:app" 2>/dev/null || true); do
      [[ -n "$p" ]] && kill -KILL "$p" 2>/dev/null || true
    done
    for p in $(pgrep -f "streamlit.*oneqmultia/ui/streamlit_app" 2>/dev/null || true); do
      [[ -n "$p" ]] && kill -KILL "$p" 2>/dev/null || true
    done
  fi
  if command -v lsof >/dev/null 2>&1; then
    _kill_port_kill "$API_PORT"
    _kill_port_kill "$ST_PORT"
    _kill_port_kill "$VITE_PORT"
  fi
fi

if [[ "$n" -eq 0 ]] && [[ "$USE_PORTS" -eq 0 ]]; then
  echo "提示: 若端口仍被占用，可执行  $0 --ports"
  echo "      若仍杀不掉，可执行      $0 --ports --force"
fi

echo "完成。"
