"""账号绑定：在调试版 Chrome 中打开助手站点，并检测登录态。不保存密码。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from oneqmultia.config.settings import Settings
from oneqmultia.core.dispatcher import _domain_match
from oneqmultia.platform_manager import crud
from oneqmultia.platform_manager.url_validator import extract_host, validate_platform_url
from oneqmultia.storage.models import PlatformConfigRow

_log = logging.getLogger(__name__)

# 登录页 URL 关键词
_LOGIN_URL_HINTS = (
    "login",
    "signin",
    "sign-in",
    "sign_in",
    "signup",
    "oauth",
    "passport",
    "accounts.google",
    "auth0",
    "/auth",
    "sso",
)

# 页面文案中的登录提示
_LOGIN_TEXT_HINTS = (
    "sign in",
    "log in",
    "登录",
    "登入",
    "註冊",
    "注册",
    "请先登录",
    "請先登入",
)


@dataclass(frozen=True)
class LoginInspectResult:
    """页面登录态推断结果。"""

    status: str  # logged_in | logged_out | unknown
    message: str


def infer_login_status(
    *,
    current_url: str,
    page_title: str = "",
    has_password_input: bool = False,
    has_input_box: bool = False,
    visible_text_sample: str = "",
) -> LoginInspectResult:
    """根据 URL、密码框、输入框和可见文案推断是否已登录。"""
    url_l = (current_url or "").lower()
    title_l = (page_title or "").lower()
    sample_l = (visible_text_sample or "").lower()[:2000]
    blob = f"{title_l} {sample_l}"

    if any(hint in url_l for hint in _LOGIN_URL_HINTS):
        return LoginInspectResult("logged_out", "当前停留在登录/授权页，尚未绑定账号")
    if has_password_input:
        return LoginInspectResult("logged_out", "检测到密码输入框，需要先完成登录")
    if has_input_box:
        return LoginInspectResult("logged_in", "已检测到对话输入框，账号可用")
    if any(hint in blob for hint in _LOGIN_TEXT_HINTS):
        return LoginInspectResult("logged_out", "页面提示需要登录")
    return LoginInspectResult("unknown", "无法确认登录态，请打开该站点完成登录后再检测")


async def open_login_tab(context: Any, url: str, timeout_ms: int) -> str:
    """在 CDP Chrome 中打开（或复用）助手页面，供用户手动登录。返回当前 URL。"""
    page = None
    for existing in context.pages:
        try:
            page_url = existing.url
        except Exception:
            continue
        if page_url and _domain_match(page_url, url):
            page = existing
            break
    if page is None:
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    else:
        try:
            await page.bring_to_front()
        except Exception:
            pass
        if page.url.startswith(("about:", "chrome:")):
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    return page.url


async def inspect_login_on_page(page: Any, selectors: dict[str, Any]) -> LoginInspectResult:
    """读取当前页 DOM，推断登录态。"""
    current_url = ""
    title = ""
    try:
        current_url = page.url or ""
        title = await page.title()
    except Exception as exc:
        return LoginInspectResult("unknown", f"无法读取页面：{exc}")

    has_password = False
    try:
        loc = page.locator("input[type='password']")
        has_password = await loc.count() > 0 and await loc.first.is_visible()
    except Exception:
        has_password = False

    has_input = False
    input_sel = (selectors or {}).get("input_box") or "textarea, [contenteditable='true']"
    try:
        loc = page.locator(input_sel)
        n = await loc.count()
        if n > 0:
            has_input = await loc.first.is_visible()
    except Exception:
        has_input = False

    sample = ""
    try:
        sample = await page.inner_text("body", timeout=3000)
    except Exception:
        sample = ""

    return infer_login_status(
        current_url=current_url,
        page_title=title,
        has_password_input=has_password,
        has_input_box=has_input,
        visible_text_sample=sample,
    )


async def check_login_status(context: Any, row: PlatformConfigRow, timeout_ms: int) -> LoginInspectResult:
    """复用已打开 Tab，必要时短暂打开再检测（新 Tab 检测后关闭以免打扰）。"""
    reused = None
    for existing in context.pages:
        try:
            page_url = existing.url
        except Exception:
            continue
        if page_url and _domain_match(page_url, row.url):
            reused = existing
            break
    if reused is not None:
        return await inspect_login_on_page(reused, row.selectors or {})

    page = await context.new_page()
    try:
        await page.goto(row.url, wait_until="domcontentloaded", timeout=timeout_ms)
        return await inspect_login_on_page(page, row.selectors or {})
    finally:
        try:
            await page.close()
        except Exception:
            pass


def persist_url_check(db: Session, row: PlatformConfigRow, result) -> PlatformConfigRow:
    """把网址校验结果写入平台行。"""
    row.url_status = result.status
    row.url_check_message = result.message
    row.url_checked_at = datetime.now(timezone.utc)
    if result.ok and result.host and not (row.expected_host or "").strip():
        row.expected_host = result.host
    db.commit()
    db.refresh(row)
    return row


def persist_login_check(db: Session, row: PlatformConfigRow, result: LoginInspectResult) -> PlatformConfigRow:
    """把登录态写入平台行。"""
    row.login_status = result.status
    row.login_message = result.message
    row.login_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def validate_and_store_url(
    db: Session,
    platform_id: str,
    *,
    check_network: bool = True,
    url_override: Optional[str] = None,
) -> PlatformConfigRow:
    """校验并落库网址状态。"""
    row = crud.get_platform(db, platform_id)
    if row is None:
        raise ValueError(f"platform not found: {platform_id}")
    target = url_override if url_override is not None else row.url
    result = validate_platform_url(
        target,
        expected_host=row.expected_host or extract_host(row.url),
        check_network=check_network,
    )
    return persist_url_check(db, row, result)


async def bind_or_check_login(
    db: Session,
    platform_id: str,
    context: Any,
    *,
    open_tab: bool,
) -> PlatformConfigRow:
    """打开登录页或仅检测登录态，并写入数据库。"""
    row = crud.get_platform(db, platform_id)
    if row is None:
        raise ValueError(f"platform not found: {platform_id}")
    if context is None:
        raise RuntimeError("CDP 未连接：请先启动调试版 Chrome（./scripts/start_chrome_cdp.sh）")
    settings = Settings()
    timeout_ms = settings.goto_timeout_ms
    if open_tab:
        await open_login_tab(context, row.url, timeout_ms)
        # 打开后立刻检测一次；用户可能尚未登录，状态允许为 logged_out
        result = await check_login_status(context, row, timeout_ms)
        if result.status == "logged_out":
            result = LoginInspectResult(
                "logged_out",
                "已在 Chrome 中打开该助手，请在弹出的标签页完成登录，然后点击「检测登录」",
            )
        return persist_login_check(db, row, result)
    result = await check_login_status(context, row, timeout_ms)
    return persist_login_check(db, row, result)
