"""平台健康检查：页面可访问性（可选 CDP）。"""

from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

from oneqmultia.config.settings import Settings
from oneqmultia.platform_manager import crud
from oneqmultia.storage.models import PlatformConfigRow


async def check_platform_url_reachable(url: str, timeout_ms: int = 15000) -> tuple[bool, str]:
    """
    使用无头浏览器快速打开 URL，判断是否可达。
    未配置 CDP 时使用独立 browser（不要求用户已登录）。
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await browser.close()
        return True, "ok"
    except Exception as e:
        return False, str(e)


async def run_health_check(
    db: Session,
    platform_id: str,
    *,
    use_cdp: Optional[bool] = None,
) -> PlatformConfigRow:
    """
    更新平台 health_status。
    use_cdp=True 时尝试 connect_over_cdp（需 Settings.cdp_url）。
    """
    row = crud.get_platform(db, platform_id)
    if row is None:
        raise ValueError(f"platform not found: {platform_id}")

    settings = Settings()
    use_cdp = use_cdp if use_cdp is not None else bool(settings.cdp_url)

    if use_cdp and settings.cdp_url:
        ok, msg = await _check_via_cdp(settings.cdp_url, row.url)
    else:
        ok, msg = await check_platform_url_reachable(row.url)

    row.health_status = "healthy" if ok else "unhealthy"
    row.health_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    if not ok:
        # 将原因写入内存属性供 API 返回（不强制落库）
        setattr(row, "_last_health_message", msg)
    return row


async def _check_via_cdp(cdp_url: str, target_url: str) -> tuple[bool, str]:
    """在已登录浏览器中打开新页签检测（简化：仅检测能否导航）。"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await page.close()
        return True, "ok"
    except Exception as e:
        return False, str(e)
