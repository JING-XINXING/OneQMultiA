# -*- coding: utf-8 -*-
"""
Streamlit MVP：问答、历史会话、平台管理三页导航。
通过 REST 调用 FastAPI，支持导出/分享。
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone, timedelta

import httpx
import streamlit as st

st.set_page_config(page_title="OneQMultiA", layout="wide", initial_sidebar_state="expanded")

# ── 样式 ────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .answer-card { border:1px solid #e0e0e0; border-radius:10px; padding:16px;
                   margin-bottom:12px; background:#fafafa; min-height:120px; }
    .answer-card.success { border-left:4px solid #2ecc71; }
    .answer-card.timeout { border-left:4px solid #f39c12; }
    .answer-card.error   { border-left:4px solid #e74c3c; }
    .answer-card.skipped { border-left:4px solid #95a5a6; }
    .card-header { font-weight:600; font-size:1.05em; margin-bottom:6px; }
    .card-time { font-size:0.78em; color:#888; margin-bottom:8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

_TZ_CN = timezone(timedelta(hours=8))
_GRID_COLS = 3
_STATUS_ICON = {"success": "✅", "timeout": "⏱️", "error": "❌", "skipped": "⏭️"}
_ASK_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)


def _fmt_ts(iso_str: str | None) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone(_TZ_CN).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(iso_str)


def _fmt_now() -> str:
    return datetime.now(_TZ_CN).strftime("%Y-%m-%d %H:%M:%S")


def _api_client(base: str) -> httpx.Client:
    return httpx.Client(base_url=base.rstrip("/"), timeout=_ASK_TIMEOUT)


def _render_answer_card(a: dict) -> None:
    status = a.get("status", "error")
    icon = _STATUS_ICON.get(status, "❓")
    name = a.get("platform_name", "")
    duration = a.get("response_duration_ms")
    dur_str = f"{duration / 1000:.1f}s" if duration else "—"
    st.markdown(
        f"""<div class="answer-card {status}">
            <div class="card-header">{icon} {name} · {status}</div>
            <div class="card-time">发送:{_fmt_ts(a.get('request_sent_at'))} |
            首字:{_fmt_ts(a.get('first_token_at'))} | 完成:{_fmt_ts(a.get('completed_at'))} | {dur_str}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    if a.get("error_message"):
        st.error(a["error_message"])
    text = a.get("answer_text", "") or ""
    if text:
        st.markdown(text)


def page_ask(client: httpx.Client, api_base: str) -> None:
    """问答主页。"""
    st.title("OneQMultiA · 问答")

    if "session_id" not in st.session_state:
        st.session_state.session_id = None

    try:
        plats = client.get("/api/platforms", params={"enabled_only": True}).json()
    except Exception as e:
        st.error(f"无法加载平台：{e}")
        return

    if st.session_state.session_id is None:
        try:
            r0 = client.post("/api/sessions", json={"title": ""})
            if r0.status_code == 200:
                st.session_state.session_id = r0.json()["id"]
        except Exception:
            pass

    labels = [f"{p['display_name']} ({p['id']})" for p in plats]
    id_by_label = {labels[i]: plats[i]["id"] for i in range(len(labels))}
    picked = st.multiselect("参与回答的平台（不选=全部）", options=labels, default=[])
    q = st.text_area("问题", height=100)

    if st.button("发送", type="primary") and q.strip():
        sid = st.session_state.session_id
        if not sid:
            r0 = client.post("/api/sessions", json={"title": ""})
            sid = r0.json()["id"] if r0.status_code == 200 else None
            st.session_state.session_id = sid
        if not sid:
            st.error("无法创建会话")
            return

        ids = [id_by_label[x] for x in picked] if picked else None
        st.info(f"提问时间: {_fmt_now()} | 问题: {q.strip()}")
        progress = st.progress(0, text="正在提问…")
        try:
            r = client.post(f"/api/sessions/{sid}/ask", json={"question": q.strip(), "platform_ids": ids})
            progress.progress(100, text="完成")
        except httpx.ReadTimeout:
            st.error("请求超时，请减少平台数量")
            return
        if r.status_code != 200:
            st.error(r.text)
            return

        data = r.json()
        summary = data.get("summary", {})
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("总计", summary.get("total", 0))
        c2.metric("成功", summary.get("success", 0))
        c3.metric("超时", summary.get("timeout", 0))
        c4.metric("出错", summary.get("error", 0))
        c5.metric("平均耗时", f"{(summary.get('avg_duration_ms') or 0) / 1000:.1f}s")

        answers = sorted(data.get("answers", []), key=lambda a: (0 if a["status"] == "success" else 1, a.get("platform_name", "")))
        st.subheader("各平台回答")
        n = len(answers)
        for row in range(math.ceil(n / _GRID_COLS)):
            cols = st.columns(_GRID_COLS)
            for ci in range(_GRID_COLS):
                idx = row * _GRID_COLS + ci
                if idx < n:
                    with cols[ci]:
                        _render_answer_card(answers[idx])

    if st.session_state.session_id:
        st.divider()
        sid = st.session_state.session_id
        fmt = st.selectbox("导出格式", ["md", "txt", "html", "pdf", "docx"])
        st.markdown(f"[下载 {fmt}]({api_base}/api/sessions/{sid}/export?format={fmt})")
        if st.button("生成分享链接"):
            sr = client.post(f"/api/sessions/{sid}/share")
            if sr.status_code == 200:
                st.code(f"{api_base}{sr.json().get('url_path', '')}")


def page_history(client: httpx.Client, api_base: str) -> None:
    """历史会话列表与详情。"""
    st.title("历史会话")
    try:
        sessions = client.get("/api/sessions").json()
    except Exception as e:
        st.error(f"加载失败：{e}")
        return

    if not sessions:
        st.info("暂无会话记录")
        return

    for s in sessions:
        with st.expander(f"{s.get('title') or '未命名'} · {_fmt_ts(s.get('updated_at'))} · `{s['id'][:8]}…`"):
            if st.button("加载此会话", key=f"load_{s['id']}"):
                st.session_state.session_id = s["id"]
                st.success(f"已切换会话 {s['id']}")
            dr = client.get(f"/api/sessions/{s['id']}")
            if dr.status_code != 200:
                st.error(dr.text)
                continue
            detail = dr.json()
            for qa in detail.get("qa_pairs", []):
                st.markdown(f"**Q** ({_fmt_ts(qa.get('question_time'))}): {qa.get('question')}")
                for a in qa.get("answers", []):
                    _render_answer_card(a)
            fmt = st.selectbox("导出", ["md", "txt", "html"], key=f"fmt_{s['id']}")
            st.markdown(f"[导出]({api_base}/api/sessions/{s['id']}/export?format={fmt})")


def page_platforms(client: httpx.Client) -> None:
    """平台管理：启用/禁用、编辑 selectors、健康检查。"""
    st.title("平台管理")
    try:
        plats = client.get("/api/platforms").json()
    except Exception as e:
        st.error(f"加载失败：{e}")
        return

    groups = sorted({p.get("group", "custom") for p in plats})
    grp_filter = st.selectbox("分组筛选", ["全部"] + groups)
    filtered = plats if grp_filter == "全部" else [p for p in plats if p.get("group") == grp_filter]

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("全部启用"):
            ids = [p["id"] for p in filtered]
            r = client.post("/api/platforms/batch-enable", json={"platform_ids": ids, "enabled": True})
            st.success(f"已启用 {r.json().get('updated', 0)} 个") if r.status_code == 200 else st.error(r.text)
            st.rerun()
    with col_b:
        if st.button("全部禁用"):
            ids = [p["id"] for p in filtered]
            r = client.post("/api/platforms/batch-enable", json={"platform_ids": ids, "enabled": False})
            st.success(f"已禁用 {r.json().get('updated', 0)} 个") if r.status_code == 200 else st.error(r.text)
            st.rerun()
    with col_c:
        if st.button("导出 JSON"):
            er = client.get("/api/platforms/export/all")
            if er.status_code == 200:
                st.download_button("下载 platforms.json", er.json()["json"], "platforms.json")

    st.divider()
    for p in filtered:
        health = p.get("health_status", "unknown")
        enabled = p.get("enabled", True)
        with st.expander(f"{'🟢' if enabled else '⚫'} {p['display_name']} ({p['id']}) · {health}"):
            new_enabled = st.toggle("启用", value=enabled, key=f"en_{p['id']}")
            if new_enabled != enabled:
                client.patch(f"/api/platforms/{p['id']}", json={"enabled": new_enabled})
                st.rerun()

            st.text_input("URL", value=p.get("url", ""), disabled=True)
            sel_json = st.text_area(
                "Selectors (JSON)",
                value=json.dumps(p.get("selectors", {}), ensure_ascii=False, indent=2),
                height=120,
                key=f"sel_{p['id']}",
            )
            if st.button("保存 Selectors", key=f"save_{p['id']}"):
                try:
                    sel = json.loads(sel_json)
                    pr = client.patch(f"/api/platforms/{p['id']}", json={"selectors": sel})
                    st.success("已保存") if pr.status_code == 200 else st.error(pr.text)
                except json.JSONDecodeError as e:
                    st.error(f"JSON 无效：{e}")

            if st.button("健康检查", key=f"hc_{p['id']}"):
                hr = client.post(f"/api/platforms/{p['id']}/health")
                if hr.status_code == 200:
                    st.json(hr.json())
                else:
                    st.error(hr.text)


# ── 主入口 ─────────────────────────────────────────────────────
st.sidebar.title("OneQMultiA")
api_base = st.sidebar.text_input("API 地址", value="http://127.0.0.1:38421").rstrip("/")
page = st.sidebar.radio("导航", ["问答", "历史会话", "平台管理"], index=0)

if st.sidebar.button("新建会话"):
    with _api_client(api_base) as c:
        r = c.post("/api/sessions", json={"title": ""})
        if r.status_code == 200:
            st.session_state.session_id = r.json()["id"]
            st.sidebar.success(f"会话: {st.session_state.session_id[:8]}…")

if st.session_state.get("session_id"):
    st.sidebar.caption(f"当前会话: `{st.session_state.session_id[:12]}…`")

try:
    with _api_client(api_base) as client:
        if page == "问答":
            page_ask(client, api_base)
        elif page == "历史会话":
            page_history(client, api_base)
        else:
            page_platforms(client)
except httpx.ConnectError:
    st.error(f"无法连接 API ({api_base})，请先启动后端。")
