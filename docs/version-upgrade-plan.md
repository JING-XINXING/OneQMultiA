# OneQMultiA 架构诊断与版本升级计划（v0.2.0 → v1.0.0）

> **文档性质**：架构审查、现状评估与分阶段演进路线图  
> **基线版本**：`v0.2.0`（Git Commit `cb3f0c4`）  
> **编制日期**：2026-11-25  
> **服务端口规范**：FastAPI `38421` · Streamlit `38422` · React/Vite `38423` · Chrome CDP `9222`

---

## 1. 执行摘要（Executive Summary）

**OneQMultiA（一问多答）** 是一套面向多源知识交叉验证场景的 AI 聚合问答系统。当前 `v0.2.0` 版本已成功跑通「**单次提问 → 多平台并发分发 → WebSocket 实时汇聚 → 最优解合成与多维对比 → 多格式导出与桌面端打包**」的完整产品闭环，内置 **23 个国内外主流 AI 平台配置**、**9 家大模型合成网关** 及 **89 项自动化测试**，具备扎实的全栈工程雏形。

与此同时，经过对后端调度核心、浏览器自动化层、存储模型、React/PWA 前端及 CI/打包链路的逐模块代码审计，当前版本在迈向高频真实生产使用时存在 **5 项 P0 级核心缺陷与安全风险**、**5 项 P1 级抓取质量与性能瓶颈** 以及 **4 项 P2 级交互与工程化短板**——集中体现在：专用适配器钩子方法未生效（死代码）、单 `BrowserContext` 并发切前台引发输入焦点抢占、首字响应时间（TTFT）埋点失真、全量配置替换无事务回滚与自动备份、DOM 纯文本提取丢失代码块/表格/公式格式，以及缺乏「Web CDP + API 直连」双模混合调度能力。

本计划提出 **三阶段演进路线图**：
- **v0.3.0（基石加固版）**：修复适配器生命周期钩子、同域并发锁与后台无焦点输入、真实 TTFT 计量、HTML→Markdown 富格式提取渲染、SQLite 自动热备、WebSocket 幂等续传及跨端导出分享闭环；
- **v0.4.0（混合引擎版）**：引入 `ApiPlatformAdapter` 实现「网页 CDP + 官方 API」双通道混合调度与自动降级，全链路异步并发化，落地可视化选择器在线测试器（`SelectorTester`）与会话全生命周期检索管理；
- **v1.0.0（生产协同与深度评测版）**：补齐局域网/远程访问鉴权、SSRF 防护与分享 TTL，升级「观点分歧矩阵 + 幻觉交叉核验 + 领域评测模板」，支持多模态文件/图片并发提问与 SQLite/PostgreSQL 双存储引擎。

---

## 2. Cursor Cloud Agent 开发工作环境配置说明

为保障 Cursor Cloud Agent 与本地开发者在零冲突环境下高效执行编码、联调、UI 验收与回归测试，已完成以下标准化环境配置：

### 2.1 运行时组件与端口映射

| 组件 / 服务 | 运行方式 / 路径 | 监听地址与端口 | 职责说明 |
|---|---|---|---|
| **Python 虚拟环境** | `.venv`（Python 3.12+） | — | 隔离安装 `.[dev,ui,packaging]` 全部依赖，避免全局包冲突 |
| **浏览器内核** | Google Chrome + Playwright Chromium | CDP 调试端口 `9222`（按需） | 无头可达性健康探测与本机已登录会话 CDP 接入 |
| **系统底层库** | `python3-venv`、`libcairo2-dev`、`lsof`、`fonts-noto-cjk` | — | 支撑虚拟环境构建、`xhtml2pdf` 渲染、端口清理与中文字体显示 |
| **FastAPI 后端服务** | `tmux` 会话 `oneqmultia-api` | `127.0.0.1:38421` | REST API、`/api/ws/ask` WebSocket 流式网关、Swagger `/docs` |
| **Streamlit 工作台** | `tmux` 会话 `oneqmultia-streamlit` | `127.0.0.1:38422` | Python 轻量运维/快速验证前端 |
| **React + Vite 前端** | `tmux` 会话 `oneqmultia-vite` | `0.0.0.0:38423` | 正式响应式 Web / PWA 工作台（自动代理 `/api` 与 WS 至 `38421`） |

### 2.2 常用开发与验证命令

```bash
# 1. 运行全量后端单元与集成测试（89 项用例）
.venv/bin/pytest test/ -q

# 2. 前端 TypeScript 类型检查与生产包构建
cd frontend && npm run build

# 3. 查看或重连后台服务 tmux 会话
tmux ls
curl -sf http://127.0.0.1:38421/health
```

---

## 3. 当前最新版本（v0.2.0）功能全景与技术特点分析

### 3.1 系统分层架构现状

```
┌────────────────────────────────────────────────────────────────────────────┐
│ 客户端展示层                                                                │
│  ├─ React 18 + TS + Tailwind + PWA (38423 / 生产同源挂载 38421)             │
│  ├─ Streamlit REST 快速控制台 (38422)                                       │
│  └─ PyInstaller 桌面启动器 desktop.py (macOS .dmg / Windows Setup .exe)    │
├────────────────────────────────────────────────────────────────────────────┤
│ API 与实时通信层 (FastAPI · 38421)                                          │
│  ├─ routes.py          会话创建、同步提问、多维对比、LLM 最优解刷新           │
│  ├─ ws_routes.py       /api/ws/ask 流式增量推送 + 全局/单平台 Cancel 控制    │
│  ├─ platform_routes.py 平台 CRUD、批量启停、JSON 导入导出、网址校验、登录扫描 │
│  └─ export_routes.py / public_routes.py  五格式导出下载 + 只读分享链接解析   │
├────────────────────────────────────────────────────────────────────────────┤
│ 核心调度与智能合成层 (src/oneqmultia/core/)                                  │
│  ├─ dispatcher.py       Semaphore(5) 并发控制、同域 Tab 复用、0.3s 取消轮询  │
│  ├─ compare.py          中文 2-gram Jaccard 相似度、三维评分、无密钥聚类合成  │
│  └─ llm_synthesizer.py  9 家厂商 OpenAI 兼容重写最优解 + SQLite 结果缓存     │
├────────────────────────────────────────────────────────────────────────────┤
│ 浏览器自动化与平台治理层                                                    │
│  ├─ GenericAdapter      keyboard/fill 注入、遮罩清理、双层备用选择器兜底      │
│  ├─ account_binder.py   不存密码的 CDP 登录页拉起与 DOM 登录态推断            │
│  └─ default_platforms.yaml  预置 23 个平台（7 国际 + 16 国内）分级超时配置   │
└────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心亮点与已落地特性评估

1. **免账密托管的 CDP 登录态复用机制**  
   通过 `playwright.chromium.connect_over_cdp` 连接独立 `--user-data-dir` 的 Chrome 实例，既规避了各 AI 站点复杂的滑块验证码、OAuth 与风控拦截，又做到了**零密码存储**；`main.py` 内置 `_cdp_reconnect_loop`（默认 30s 周期）实现浏览器重启后的无感自动重连。
2. **高容错通用网页适配器（`GenericAdapter`）**  
   针对现代 SPA 框架（React/Vue/ProseMirror/Quill）设计了多项实战容错策略：
   - **合成事件输入**：支持 `Control+a` + `Backspace` + 逐字 `type` 激活前端受控组件状态；
   - **入口路径自愈**：`page_nav.py` 的 `should_open_entry_url()` 能在复用 Tab 停留在营销根路径时自动拉回 `/chat`、`/#/chat`、`/home` 等对话入口；
   - **原地更新兼容**：`is_new_answer()` 同时对比响应节点数与末条文本快照，解决了豆包、Pi、灵光等原地更新 DOM 节点不新增的问题；
   - **思考态防误判**：`_looks_incomplete()` 过滤 `Thinking...`、`思考中` 等短占位文案，防止推理模型在思考阶段被误判为输出稳定而提前截断。
3. **「零配置可用 + 大模型增强」双引擎最优解架构**  
   未配置任何 API Key 时，`compare.py` 基于中文字符二元语法（2-gram Jaccard）计算共识度并聚类出「共识要点 + 补充视角 + 推荐原文」；配置任一厂商密钥（DeepSeek、Kimi、通义千问、智谱 GLM、MiniMax、豆包、LongCat、小米 MiMo、OpenAI 兼容）后自动升级为大模型精编答案，且将合成结果缓存至 `qa_pairs.optimal_answer` 字段避免历史回看重复计费。
4. **良好的工程交付形态与测试基线**  
   - `paths.py` 清晰分离了开发态仓库路径与 PyInstaller 冻结态（`sys._MEIPASS` 只读资源 + 系统用户目录可写库/日志）；
   - `export_service.py` 妥善处理了 Starlette Latin-1 Header 限制下的 RFC 5987 中文附件名编码；
   - `test/` 目录覆盖了 25 个测试文件、89 个测试用例，执行耗时仅约 `1.4s`。

---

## 4. 现存问题与不足之处深度剖析（按严重度分级）

以下全部问题均基于 `v0.2.0` 源码逐一定位验证：

### 4.1 P0 级问题：功能失效、并发竞态与数据/安全风险

| 编号 | 问题摘要 | 涉及源码位置 | 根因分析与实际影响 |
|---|---|---|---|
| **P0-1** | **专用适配器钩子方法为「死代码」，完全未生效** | `platforms/specialized/{chatgpt,deepseek,kimi}.py`<br>`platforms/generic.py` | 三个专用适配器均重写了 `async def send_question(self, page, question)` 并调用 `await super().send_question(...)`，但 `BasePlatformAdapter` 与 `GenericAdapter` 仅定义了 `ask()`，**不存在 `send_question` 方法**。运行时 `adapter.ask()` 直接走 `GenericAdapter.ask()`，专用逻辑从未被执行；一旦外部直接调用 `send_question` 还会抛出 `AttributeError`。 |
| **P0-2** | **多平台共享单 `BrowserContext` 抢占前台焦点与同域 Tab 竞态** | `core/dispatcher.py` (`_get_or_open_page`, L89–111) | 最高 5 个平台协程并发执行 `await page.bring_to_front()` 后紧接着模拟物理键盘 `box.type()`，窗口焦点在毫秒级来回切换会导致输入字符丢失、半截发送甚至串台；同时若两个平台同主域或多客户端并发提问，会命中同一 `Page` 对象引发严重读写冲突。 |
| **P0-3** | **首字响应时间（TTFT / `first_token_at`）埋点错误** | `platforms/generic.py` (L351–356) | `timing.first_token_at = datetime.now(timezone.utc)` 写在 `_fill_input()` 之后、`_send_message()` **之前**，实际记录的是「本地填完输入框的时刻」，而非 AI 平台产出首个字符的时刻，导致所有首字耗时指标失真。 |
| **P0-4** | **数据库迁移与全量导入无自动备份、无原子回滚** | `platform_manager/importer.py` (`import_json_replace`)<br>`storage/migrate.py`<br>`tools/reset_db.py` | `import_json_replace()` 先遍历删除全部平台并执行 `db.commit()`，再循环插入新记录——一旦中途某条记录字段缺失或格式非法，**原有 23 个平台配置将永久清空且无法回滚**；`migrate.py` 执行 `ALTER TABLE` 前未对 `oneqmultia.db` 做快照备份。 |
| **P0-5** | **公开分享页面缺失 UI 渲染，远程访问缺乏鉴权与 SSRF 防护** | `main.py` (`allow_origins=["*"]`)<br>`sharing/share_service.py`<br>`platform_manager/url_validator.py` | ① 前端复制的分享链接为 `/api/public/share/{token}`，用户打开看到的是裸 JSON 而非可视化网页，且分享链接无过期时间与撤销能力；② 开启局域网/公网监听（`0.0.0.0`）供手机访问时，平台删除、覆盖导入、操控宿主机打开 Chrome（`/login/open`）及消耗额度的 `/compare/refresh` 均无鉴权与限流；③ `check_url_reachable()` 未屏蔽 `127.0.0.1`、`169.254.169.254`、`10.0.0.0/8` 等内网地址。 |

### 4.2 P1 级问题：内容质量损耗、性能阻塞与多轮上下文污染

| 编号 | 问题摘要 | 涉及源码位置 | 根因分析与实际影响 |
|---|---|---|---|
| **P1-1** | **`inner_text()` 提取丢失代码块、表格、公式与超链接** | `platforms/generic.py` (`_tail_text`, `_get_response_text`)<br>`frontend/src/components/{AnswerCard,OptimalAnswer}.tsx` | 采集端使用 `locator.inner_text()` 将富结构 DOM 压平为纯文本，丢失 Markdown 代码语言标记、表格边框、行内代码与链接；展示端仅用 `whitespace-pre-wrap` 纯文本渲染，在编程问答、生信数据分析与文献整理场景下可读性大幅下降。 |
| **P1-2** | **PDF 导出缺少中文字体注册，易产生方块乱码** | `export/pdf_exporter.py`<br>`export/html_exporter.py` | `xhtml2pdf` 底层依赖 ReportLab，默认 Helvetica 字体不含 CJK 字形；`session_to_html()` 仅写了 `font-family: system-ui` 而未为 pisa 注册 TTF/OTF 中文字体映射，导出中文会话 PDF 时极易出现黑块（`■`）。 |
| **P1-3** | **同步阻塞调用混入异步路由，批量扫描串行耗时过长** | `core/llm_synthesizer.py` (`_chat_complete`)<br>`platform_manager/url_validator.py`<br>`api/platform_routes.py` (`scan_accounts`)<br>`platform_manager/health_checker.py` | ① `scan_accounts` 在 `async def` 路由中对 23 个平台串行调用同步 `urlopen(timeout=12)` 并逐一开关 Tab，弱网下耗时可达 3–4 分钟并阻塞整个 FastAPI 事件循环；② `llm_synthesizer` 使用同步 `httpx.Client(timeout=75)` 整包等待，不支持流式生成；③ `health_checker` 每次检查单个平台都冷启动并销毁整个 Chromium 实例。 |
| **P1-4** | **新建会话未触发平台端开启新对话，上下文跨会话串扰** | `config/default_platforms.yaml` (`new_chat_button: ""`)<br>`platforms/generic.py` | 23 个预置平台的 `new_chat_button` 全部为空；当用户在 OneQMultiA 新建会话提问时，复用的浏览器 Tab 仍追加在旧聊天记录下方，导致各 AI 模型受无关历史上下文干扰。 |
| **P1-5** | **缺少「Web CDP + 官方 API」双通道混合分发能力** | `platforms/base.py`<br>`core/llm_catalog.py` | 系统虽已在 `.env` 支持配置 9 大厂商 API Key，但仅用于事后「最优答案重写」，未能支持将已配 Key 的平台直接作为高速稳定的 API 数据源参与一问多答，也无法在网页 DOM 改版失效时自动回退 API。 |

### 4.3 P2 级问题：前端功能缺口、移动端体验断层与工程门禁不足

| 编号 | 问题摘要 | 涉及源码位置 | 根因分析与实际影响 |
|---|---|---|---|
| **P2-1** | **前端平台管理与原规划能力存在明显缺口** | `frontend/src/components/platform-manager/*` | 后端已具备创建、删除、导入、导出 API，但 React 前端仅能「开关启用」和「修改网址/JSON 选择器」，无法在界面上新增自定义平台、删除失效平台、调整排序、按国际/国内分组筛选、导入导出备份，也缺少可视化「选择器在线测试器」。 |
| **P2-2** | **移动端缺失导出与分享入口，历史会话不可管理** | `frontend/src/layouts/MobileLayout.tsx`<br>`frontend/src/components/SessionHistory.tsx` | `ExportMenu` 仅挂载在桌面端 `DashboardSidebar` 中，`MobileLayout` 未渲染侧边栏导致**手机端完全无法导出文档或生成分享链接**；同时双端历史列表均不支持重命名、删除单条会话或按关键词搜索。 |
| **P2-3** | **WebSocket 断线重连会触发重复提问，PWA 缓存易卡旧包** | `frontend/src/hooks/useWebSocketAsk.ts`<br>`frontend/public/{service-worker.js,manifest.json}` | ① WS 意外断开自动重连时重新发送 `action: "ask"`，导致同一问题在数据库重复生成 `QAPairRow` 并向各平台二次发送；② `service-worker.js` 对 `/` 和 `/index.html` 采用永久 `cache-first`，发版后用户端难以自动刷新；`manifest.json` 未挂载已有的 `192x192` / `512x512` PNG 图标。 |
| **P2-4** | **脚本跨平台兼容、CI 前端门禁与文档同步滞后** | `scripts/start_chrome_cdp.sh`<br>`.github/workflows/ci.yml`<br>`pyproject.toml` | ① `start_chrome_cdp.sh` 写死 macOS Chrome 路径，Linux 下不可用；② GitHub Actions `ci.yml` 未检查 `frontend` 编译与类型安全；③ `pytest-asyncio` 存在 `asyncio_default_fixture_loop_scope` 告警；④ `docs/development-plan.md` 与 `v0.2.0` 实际演进状态脱节。 |

---

## 5. 下一步开发优化计划（分版本升级路线图）

遵循「**先稳基石、再提效率、后拓生态**」的工程演进原则，制定 `v0.3.0` → `v0.4.0` → `v1.0.0` 三阶段版本升级计划。

---

### 阶段一：`v0.3.0` —— 核心稳定性、数据安全与跨端体验闭环（基石加固版）

**版本目标**：清零所有 P0 级缺陷，解决并发串台、专用适配器失效、纯文本丢格式、数据库无备份及移动端断层问题，让日常多平台问答稳定可靠。

#### 模块 1.1：适配器协议重构与无干扰并发调度
- **重构 `BasePlatformAdapter` 模板方法生命周期**：在 `GenericAdapter.ask()` 内拆分为标准可覆写钩子：
  `prepare_page()` → `ensure_conversation_mode()` → `locate_input()` → `fill_question()` → `submit_question()` → `stream_response()`，彻底激活 `ChatGPTAdapter`、`DeepSeekAdapter`、`KimiAdapter` 的定制前处理与提取逻辑。
- **消除焦点抢占与同域竞态**：
  - 在 `dispatcher.py` 引入按归一化主域名的 `asyncio.Lock` 注册表与 `Page` 租约标记（`in_use_pages`），同一时刻同一 `Page` 严格单协程独占；
  - 移除常规问答路径中的 `page.bring_to_front()`，改用 DOM `dispatchEvent` / `insertText` / Playwright Locator 定向事件注入，仅在特定平台确需前台激活时通过全局短时焦点互斥锁（`focus_lock`）串行完成输入动作。
- **精准 TTFT 计量与新对话隔离**：
  - 将 `timing.first_token_at` 移至 `_get_response_text()` **首次捕获到非空且非思考态的新增字符瞬间**；
  - 为预置平台补齐 `selectors.new_chat_button`，当检测到 `qa_pair` 为当前 `Session` 首问时自动触发「开启新对话」或导航至全新对话 URL。

#### 模块 1.2：富文本 Markdown 保真采集与前端排版升级
- **采集端 HTML → Markdown 保真提取**：在 `generic.py` 新增 `_extract_markdown(locator)`，在浏览器上下文内通过轻量 DOM 遍历脚本将 `<pre><code>`（提取 `language-*` 类名）、`<table>`、`<ul>/<ol>`、`<h1>-<h6>`、`<a>`、`<strong>/<em>` 及 KaTeX/MathJax 公式节点还原为标准 GFM Markdown，失败时平滑降级 `inner_text()`。
- **展示端富文本安全渲染**：React 前端 `AnswerCard` 与 `OptimalAnswer` 引入轻量 Markdown 渲染管线（开启 HTML 转义防 XSS），支持代码块语法高亮、一键复制代码按钮、响应式表格及折叠长文平滑过渡。

#### 模块 1.3：数据库自动热备与原子化配置导入
- **新增 `src/oneqmultia/storage/backup.py`**：基于 Python 标准库 `sqlite3.Connection.backup()` 实现在线热备份，生成 `data/backups/oneqmultia_YYYYMMDD_HHMMSS_<reason>.db`（默认保留最近 10 份，支持一键恢复 CLI `python -m oneqmultia.tools.restore_db`）。
- **强制前置备份触发点**：在 `migrate_schema()` 检测到待执行 `ALTER TABLE` 前、`import_json_replace()` 覆盖平台前、`reset_db.py` 重置前**自动创建备份**（严格落实数据库变更前必备份规范）。
- **单事务原子导入**：重构 `import_json_replace()`，先用 Pydantic `PlatformCreateBody` 全量校验输入数组，校验通过后在同一个数据库事务内执行替换，任一异常自动 `rollback()`。

#### 模块 1.4：WebSocket 幂等续传、分享页闭环与中文字体 PDF
- **WS 任务解耦与幂等订阅**：服务端将正在执行的问答轮次登记到内存 `ActiveRunRegistry(qa_pair_id)`，客户端断线重连后发送 `{"action": "subscribe", "qa_pair_id": "..."}` 衔接实时流与历史缓冲事件，杜绝重复提问。
- **前端公开分享视图与移动端对齐**：
  - 前端新增只读分享模式（识别 `/share/{token}` 或 `?share={token}`），美观展示问题、最优答案与各平台对比卡片；
  - 移动端底部栏或会话顶栏补齐 `ExportMenu` 抽屉，实现桌面与手机功能 100% 对等；
  - `pdf_exporter.py` 自动探测系统 CJK 字体（macOS `PingFang`/`STHeiti`、Windows `msyh.ttc`、Linux `NotoSansCJK`）并注册到 ReportLab/xhtml2pdf；
  - 统一 `scripts/start_chrome_cdp.sh` 支持 macOS 与 Linux 自动寻路；完善 `.github/workflows/ci.yml` 增加前端 `npm ci && npm run build` 与 Ruff 检查，消除 `pytest-asyncio` 配置告警。

---

### 阶段二：`v0.4.0` —— 双模混合引擎与可视化平台治理（效率跃迁版）

**版本目标**：打通「Web 网页端 + 官方 API」双通道并发能力，全链路异步化消除阻塞，打造零代码可视化平台接入与调试体验。

#### 模块 2.1：Web CDP + API 直连双通道混合调度引擎
- **新增 `ApiPlatformAdapter(BasePlatformAdapter)`**：复用并扩展 `llm_catalog.py`，支持 OpenAI Chat Completions 兼容接口、Anthropic Messages 与 Google Gemini API，通过 `httpx.AsyncClient` 原生 SSE 流式接收 `answer_delta`，精确记录真实网络 `first_token_at` 与 `usage.total_tokens`。
- **三种平台执行模式（`execution_mode`）**：
  1. `web_only`：仅走 Chrome CDP 网页自动化（适合未开放或昂贵 API 站点）；
  2. `api_only`：仅走 API 直连（无须启动 Chrome，服务器/容器环境开箱即用，首字延迟 `< 800ms`）；
  3. `web_with_api_fallback`（智能混合）：优先复用免费/包月网页端登录态，若遇 CDP 未连接、选择器失效或风控超时，自动无缝降级至已配置的 API Key 完成回答。

#### 模块 2.2：全链路异步并发改造与流式最优解
- **`llm_synthesizer.py` 异步流式化**：改造为 `async def stream_synthesize_with_llm()`，通过 WebSocket 新增 `optimal_start` / `optimal_delta` / `optimal_done` 事件，在各平台回答完毕后即时流式呈现最优答案生成过程，告别长达数十秒的白屏骨架等待。
- **并发平台体检引擎**：将 `url_validator.py` 迁移至 `httpx.AsyncClient`，`scan_accounts` 与批量健康检查通过 `asyncio.Semaphore(6)` 并发执行，并复用应用级常驻无头浏览器上下文，将 23 个平台全量扫描耗时从分钟级压缩至 **5 秒以内**。

#### 模块 2.3：完整平台管理工作台与在线选择器测试器（`SelectorTester`）
- **补齐前端平台全生命周期 UI**：支持在 React 工作台直接新增自定义平台、删除平台、拖拽/权重调整显示顺序、国际/国内/API 分组筛选、一键导入导出 JSON/YAML 配置包（导入前自动提示已生成数据库备份）。
- **可视化 `SelectorTester` 调试面板**：新增后端 `POST /api/platforms/{id}/test-selectors` 接口与前端调试抽屉，输入候选 `input_box` / `send_button` / `response_container` 选择器后，实时返回 CDP 页面匹配元素数量、可见性、首条提取文本预览及高亮框选截图，彻底解决站点改版后盲改选择器的痛点。

#### 模块 2.4：会话管理增强与全文检索
- 新增 `PATCH /api/sessions/{id}`（自定义重命名、置顶标记）、`DELETE /api/sessions/{id}`（单条/批量清理空或旧会话）与 `GET /api/sessions/search?q=...`（基于 SQLite FTS5 检索历史问题、平台回答与最优解内容）。
- PWA `service-worker.js` 升级为：HTML 导航请求采用 `network-first`（离线回退缓存），带哈希指纹的 `/assets/*` 采用 `cache-first`，补全 `manifest.json` 的 `192x192` 与 `512x512` 多尺寸图标。

---

### 阶段三：`v1.0.0` —— 生产级安全协同、深度评测矩阵与多模态旗舰版（架构升维版）

**版本目标**：满足团队共享部署、科研/工程高可信交叉核验与多模态复杂任务需求，达到正式 `1.0` 生产级交付标准。

#### 模块 3.1：安全边界加固与远程/局域网访问治理
- **分级访问控制**：默认本机回环（`127.0.0.1`）免密直连；当绑定非回环地址（如 `0.0.0.0` 供手机或团队局域网访问）时，自动启用 Bearer Access Token / 访问口令中间件，保护平台变更、宿主机浏览器拉起与付费模型调用接口。
- **SSRF 防护与速率限制**：在 `url_validator.py` 解析 DNS 后拦截回环、私网（RFC 1918）、链路本地（`169.254.0.0/16`）与 IPv6 内网地址；对公开路由 `/api/public/share/{token}` 与问答触发接口实施基于令牌桶的限流保护。
- **可控分享生命周期**：`share_links` 表扩展 `expires_at`（支持 24h / 7d / 30d / 永久）、`revoked_at` 与 `view_count`，支持在侧边栏随时查看并一键吊销已发出的分享链接。

#### 模块 3.2：结构化深度评测与幻觉交叉核验（Judge & Consensus Matrix）
- **多维交叉核验输出**：将单一文本合并升级为结构化决策面板：
  - **共识事实区**：多平台一致确认的核心结论（附支持平台徽章）；
  - **分歧与潜在幻觉预警区**：自动标出各模型在数值、API 参数、文献引用或因果推论上的矛盾点；
  - **五维量化评分卡**：按准确性、逻辑完备度、结构清晰度、代码/公式规范度、响应速度对各平台打分。
- **场景化合成模板库**：内置「通用问答」「代码架构评审」「生物信息学与科研文献综述」「商业调研对比」四套专业合成 Prompt 模板，并支持用户自定义模板。

#### 模块 3.3：多模态提问与可观测性底座
- **文件与图像并发分发**：支持在提问框粘贴截图或上传 PDF/DOCX/CSV/FASTA/代码文件，API 通道直传多模态消息或解析文档上下文，Web CDP 通道通过 `page.set_input_files()` 自动挂载附件。
- **双数据库引擎与可观测性面板**：引入标准版本化迁移与连接池调优，支持一键切换 PostgreSQL 应对团队高并发历史归档；新增「平台健康度与性能看板」，统计各平台近 7 日成功率、中位 TTFT、P95 总耗时与选择器失效告警。

---

## 6. 里程碑排期对比与关键量化验收指标（KPIs）

| 评估维度 | 当前基线（`v0.2.0`） | `v0.3.0` 目标 | `v0.4.0` 目标 | `v1.0.0` 目标 |
|---|---|---|---|---|
| **问答接入通道** | 仅 Web CDP 爬虫 | Web CDP（修复钩子 + 无焦点锁） | **Web CDP + 官方 API 混合双模** | 双模 + 多模态附件/图像并发 |
| **并发焦点稳定性** | 多 Tab `bring_to_front` 易丢字/串台 | 同域互斥锁 + 后台合成输入，**0 串台** | Web/API 独立信号量分级调度 | 支持多用户任务队列隔离 |
| **回答格式保真度** | `inner_text` 纯文本（丢代码/表格） | **HTML→GFM Markdown 富格式渲染** | 流式 Markdown + 最优解流式生成 | 结构化分歧矩阵 + 幻觉冲突高亮 |
| **TTFT 指标精度** | 记录填框完成时间（失真） | 真实首字符到达时间（误差 `< 200ms`） | API 通道首 Token 精度 `< 20ms` | 历史 P50/P95 TTFT 趋势监控 |
| **23 平台批量扫描耗时** | 串行阻塞，最坏 `> 180s` | 异常超时收敛 `< 30s` | **全异步并发扫描 `< 5s`** | 后台定时巡检 + 失效主动预警 |
| **数据库备份安全** | 无自动备份，全量导入非原子 | **变更/导入前自动热备 + 原子回滚** | UI 一键备份/快照恢复 | SQLite + PostgreSQL 双引擎 |
| **移动端与分享体验** | 手机缺导出入口；分享返回裸 JSON | **双端功能 100% 对齐 + 独立分享页** | Selector 在线可视化调试器 | 分享链接有效期/撤销 + 远程鉴权 |
| **自动化测试覆盖** | 89 项后端测试（无前端 CI） | `>= 120` 项（含前端构建与富文本测试） | `>= 155` 项（含 API 适配器与并发测试） | `>= 190` 项（含安全/E2E 回归套件） |

---

## 7. 新功能模块配套测试与验收方案

所有新增测试代码统一归档于项目 `test/` 子目录下，使用项目虚拟环境 `.venv/bin/pytest` 与前端构建工具链执行：

### 7.1 单元测试与集成测试规划（`test/`）

1. **`test/test_adapter_lifecycle.py`（v0.3.0 适配器钩子与 TTFT 测试）**
   - 构造 Mock Playwright `Page`，验证 `ChatGPTAdapter`、`DeepSeekAdapter`、`KimiAdapter` 的前置钩子被 `ask()` 正确调用；
   - 模拟延迟 800ms 后分三次流式吐出 DOM 文本，断言 `request_sent_at < first_token_at < completed_at` 且 `first_token_at` 晚于 `_send_message()`；
   - 验证会话首问自动点击 `new_chat_button`，同会话第二问保持上下文不点击。
2. **`test/test_dispatcher_concurrency.py`（v0.3.0 同域锁与幂等订阅测试）**
   - 并发派发两个同域名平台与三个异域名平台，断言同一 `Page` 实例不会发生交错写入，且常规路径不调用 `bring_to_front()`；
   - 模拟 WebSocket 半途断连后携带 `qa_pair_id` 发送 `action="subscribe"`，断言数据库仅存在 1 条 `QAPairRow` 且后续 `platform_done` 事件完整送达。
3. **`test/test_markdown_extraction_and_pdf.py`（v0.3.0 富文本采集与中文 PDF 测试）**
   - 使用 Playwright 无头 Chromium 加载内嵌代码块、表格、公式与超链接的静态 HTML 夹具，断言 `_extract_markdown()` 完整保留 ```` ```python ```` 围栏与 Markdown 表格语法；
   - 调用 `export_session(session, "pdf")` 导出含中文生僻字与多轮问答的会话，使用 `pypdf` / `pdfplumber` 提取生成的 PDF 文本，断言中文字符 100% 可读无乱码。
4. **`test/test_db_backup_and_atomic_import.py`（v0.3.0 数据库备份与回滚测试）**
   - 构造包含第 5 条非法 URL 的平台导入数组调用 `POST /api/platforms/import`，断言接口返回 `400/422`、原数据库 23 条平台配置毫发无损，且 `data/backups/` 下已自动生成前置热备文件。
5. **`test/test_hybrid_api_adapter.py` & `test/test_selector_tester.py`（v0.4.0 混合引擎与调试器测试）**
   - 基于 `httpx.MockTransport` 模拟 SSE 流式响应，验证 `ApiPlatformAdapter` 在 `api_only` 与 `web_with_api_fallback`（模拟网页选择器超时后自动切 API）两种模式下的状态流转与 Token 统计；
   - 验证 `/api/platforms/{id}/test-selectors` 对命中/未命中选择器的结构化诊断返回。
6. **`test/test_security_and_share_ttl.py`（v1.0.0 安全边界测试）**
   - 验证 `url_validator` 拦截 `http://127.0.0.1:38421`、`http://169.254.169.254/latest/meta-data` 等内网 SSRF 探测地址；
   - 验证过期或已撤销的分享 `token` 访问 `/api/public/share/{token}` 返回 `404/410`；验证非回环模式下未携带访问令牌的管理写操作返回 `401`。

### 7.2 标准验证执行清单

```bash
# 后端全量回归测试
.venv/bin/pytest test/ -v --tb=short

# 前端类型检查与生产构建验证
cd frontend && npm run build

# 桌面端（1440×900）与手机端（390×844）双视口 UI 验收
# 启动 API(38421) + Vite(38423) 后，验证问答流式卡片、最优答案渲染、移动端导出抽屉与只读分享页
```

---

## 8. 风险评估与应对策略

| 风险项 | 触发可能性 | 影响程度 | 工程应对预案 |
|---|---|---|---|
| **第三方 AI 网页端高频改版 DOM 结构** | 高 | 中 | `v0.4.0` 提供可视化 `SelectorTester` 30 秒内热修复选择器，并支持一键开启 `web_with_api_fallback` 自动回退官方 API 保障业务不中断。 |
| **浏览器多 Tab 常驻内存膨胀** | 中 | 中 | 引入空闲 Tab LRU 自动休眠/回收策略（例如超过 15 分钟未提问的后台平台 Tab 自动关闭，下次提问按需重建，保留 Cookie 登录态）。 |
| **部分站点反自动化检测拦截合成事件** | 中 | 中 | 在平台 `interaction` 配置中支持细粒度 `require_foreground: true` 标记，仅对强校验站点启用全局串行短时焦点锁，兼顾兼容性与无感并发。 |
| **数据库结构升级损坏历史问答资产** | 低 | 高 | 严格执行「无备份不迁移」铁律，`storage/backup.py` 在任何 DDL 或批量覆盖操作前强制落盘一致性快照并校验文件可读性。 |
