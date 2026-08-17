# OneQMultiA

一问多答：将同一问题并发分发到多个 AI 网页端，聚合回答。

## 安装包（Windows / macOS）

双击安装后会启动本地服务（默认 `http://127.0.0.1:38421`）并打开界面。数据与 `.env` 写在用户目录，不会进安装目录：

- macOS：`~/Library/Application Support/OneQMultiA`
- Windows：`%APPDATA%\OneQMultiA`

本机构建：

```bash
# macOS → release/OneQMultiA-*-macos.dmg
chmod +x scripts/build_macos.sh && ./scripts/build_macos.sh

# Windows（PowerShell）→ release/OneQMultiA-*-win64-setup.exe
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

Windows 安装包也可在 GitHub Actions 的 `Release installers` 工作流中构建。安装后请用 Google Chrome 登录各 AI 站点（应用会尝试拉起调试端口 9222 的独立 profile）。

## 快速开始

```bash
cd /path/to/OneQMultiA
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

### 一键启动（推荐）

在项目根目录执行（需已 `pip install -e ".[ui]"` 以便 Streamlit）：

```bash
./scripts/start_oneqmultia.sh
```

- 默认同时启动 **API**（`http://127.0.0.1:38421`）与 **Streamlit**（`http://127.0.0.1:38422`），日志在 `.run/api.log`、`.run/streamlit.log`。
- 仅 API：`./scripts/start_oneqmultia.sh --api-only`
- 再加 React 前端：`./scripts/start_oneqmultia.sh --with-vite`（需 `frontend` 已 `npm install`）
- 停止：**Ctrl+C**；或 **`./scripts/stop_oneqmultia.sh`**（读 `.run/pids` 结束子进程）
- 无 pids 文件时兜底：`./scripts/stop_oneqmultia.sh --ports`（`lsof` 释放 38421/38422/38423）
- 仍杀不掉：`./scripts/stop_oneqmultia.sh --ports --force`（`SIGKILL`）

环境变量（可选）：`ONEQMULTIA_API_HOST`、`ONEQMULTIA_API_PORT`、`ONEQMULTIA_STREAMLIT_PORT`。

### 运行 API（手动）

```bash
pip install -e .
uvicorn oneqmultia.main:app --reload
```

文档：<http://127.0.0.1:38421/docs>

- WebSocket 提问：`ws://127.0.0.1:38421/api/ws/ask`（首条 JSON：`action=ask`, `session_id`, `question`, `platform_ids`）
- 导出：`GET /api/sessions/{id}/export?format=md|txt|html|pdf|docx`
- 分享：`POST /api/sessions/{id}/share` → `GET /api/public/share/{token}`

### Streamlit（REST 界面）

```bash
pip install -e ".[ui]"
streamlit run src/oneqmultia/ui/streamlit_app.py
```

### React + Vite（WebSocket 流式）

```bash
cd frontend && npm install && npm run dev
```

浏览器打开 `http://127.0.0.1:38423`，需同时运行本机 `uvicorn`（Vite 会把 `/api` 与 WS 代理到 38421）。

### 测试

**务必使用项目 `.venv` 的解释器**，不要用全局/anaconda 的 `pytest`（其插件如 napari 可能因 numba/numpy 版本冲突导致 `ImportError`，与本项目无关）：

```bash
# 方式一：激活 venv 后再跑（推荐，提示符会显示 (.venv)）
cd /path/to/OneQMultiA
source .venv/bin/activate
pytest test/ -q

# 方式二：直接用 venv 里的 pytest，无需激活
cd /path/to/OneQMultiA
.venv/bin/pytest test/ -q
```

> 若直接运行 `pytest` 报 `Numba needs NumPy 1.26 or less` 等错误，通常是 shell 解析到了 anaconda 全局的 `pytest`（可用 `which pytest` 确认）。改用上面 `.venv` 的方式即可。

### 环境变量

| 变量 | 说明 |
|------|------|
| `ONEQMULTIA_DATABASE_URL` | SQLite 路径，默认 `sqlite:///./data/oneqmultia.db` |
| `ONEQMULTIA_CDP_URL` | **要真实驱动网页聊天必填**：已开启远程调试的 Chrome 地址，如 `http://127.0.0.1:9222` |
| `ONEQMULTIA_GOTO_TIMEOUT_MS` | 打开各平台首页超时（毫秒），默认 `90000`；仍超时可试 `120000` |
| `ONEQMULTIA_GOTO_WAIT_UNTIL` | Playwright `page.goto` 的 `wait_until`：`domcontentloaded`（默认）、`load`、`networkidle`、`commit` |

若出现 **`Page.goto: Timeout ... exceeded`**：多为当前网络访问不了该 URL（例如海外访问国内站需代理），或页面长期不触发 `domcontentloaded`；可只对已勾选的、能打开的站点提问，或在 API 中禁用打不开的 `platform_id`。

未设置 `ONEQMULTIA_CDP_URL` 时，问答接口仍会返回 200，但各平台状态为 `skipped`（与 Streamlit 里看到的一致）。

### 设置 `ONEQMULTIA_CDP_URL`（macOS 示例）

OneQMultiA 通过 [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) 接入**你已登录各 AI 网站**的 Chrome，而不是用无头浏览器重新登录。

> **重要概念**：`ONEQMULTIA_CDP_URL` 是**一个**指向「带远程调试的 Chrome」的地址，**不是每个平台配一个**。所有 AI 平台共用这一个 Chrome，你在其中分别登录各家网站即可。

1. **启动调试版 Chrome（推荐用一键脚本）**：独立 profile，不影响日常 Chrome，端口默认 9222。

   ```bash
   ./scripts/start_chrome_cdp.sh
   # 自定义端口：ONEQMULTIA_CDP_PORT=9333 ./scripts/start_chrome_cdp.sh
   ```

   手动等价命令（如需自行控制参数）：

   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=9222 \
     --user-data-dir="$HOME/chrome-oneqmultia-profile"
   ```

2. **在弹出的 Chrome 窗口里登录目标站点**：逐个打开并登录 ChatGPT、DeepSeek、Kimi、豆包、通义千问等。登录态会持久化到该 profile（`~/chrome-oneqmultia-profile`），下次无需重登。建议把常用平台 Tab 都开着——调度器会优先复用已打开的同域名 Tab，速度更快。

3. **配置环境变量并重启 API**（`uvicorn` 只在启动时读配置，改完必须重启）。项目根目录 `.env`（已支持 `pydantic-settings` 读取，默认已写好）：

   ```env
   ONEQMULTIA_CDP_URL=http://127.0.0.1:9222
   ```

   然后重启服务：

   ```bash
   ./scripts/stop_oneqmultia.sh --ports
   ./scripts/start_oneqmultia.sh          # 或 --with-vite
   ```

4. **验证**：启动日志（`.run/api.log`）应出现 `已连接 CDP 浏览器：http://127.0.0.1:9222`。再到 Streamlit（`http://localhost:38422`）或 React（`http://localhost:38423`）提问，各平台状态应从 `skipped` 变为 `success`（仍依赖该站已登录且 `selectors` 与当前 DOM 一致）。

**注意事项**：

- 调试版 Chrome 必须**一直保持运行**；关掉后 CDP 连接会断。API 已内置**自动重连**（默认每 30s 尝试，见 `ONEQMULTIA_CDP_RECONNECT_INTERVAL_SEC`），重新开启 Chrome 后无需重启 API 即可恢复。
- 跨境站点（如 ChatGPT）需本机能正常访问（代理/VPN）。
- 某平台页面改版导致选择器失效时，会返回 `error`，在「平台管理」页修改 `selectors` 即可，无需改代码重启。

首次启动会自动写入预置平台配置（若库为空）。
