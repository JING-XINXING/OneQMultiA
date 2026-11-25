"""在已连接的 CDP 页面上试跑选择器，返回命中数量和文本预览。"""

from __future__ import annotations

from typing import Any

from playwright.async_api import Page


async def probe_selectors(page: Page, selectors: dict[str, Any]) -> dict[str, Any]:
    """对 input_box / send_button / response_container 做只读探测。"""
    report: dict[str, Any] = {}
    for key in ("input_box", "send_button", "response_container"):
        selector = str((selectors or {}).get(key) or "").strip()
        if not selector:
            report[key] = {"selector": "", "count": 0, "visible": 0, "preview": "", "ok": False}
            continue
        try:
            loc = page.locator(selector)
            count = await loc.count()
            visible = 0
            preview = ""
            sample = min(count, 8)
            for index in range(sample):
                node = loc.nth(index)
                try:
                    if await node.is_visible():
                        visible += 1
                        if not preview:
                            preview = ((await node.inner_text()) or "")[:180]
                except Exception:
                    continue
            report[key] = {
                "selector": selector,
                "count": count,
                "visible": visible,
                "preview": preview.strip(),
                "ok": visible > 0,
            }
        except Exception as exc:
            report[key] = {
                "selector": selector,
                "count": 0,
                "visible": 0,
                "preview": "",
                "ok": False,
                "error": str(exc),
            }
    return report
