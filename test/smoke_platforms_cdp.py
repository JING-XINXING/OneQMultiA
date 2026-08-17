# -*- coding: utf-8 -*-
"""
预置平台 CDP 冒烟测试脚本。

用法（需已启动带远程调试的 Chrome 并设置 ONEQMULTIA_CDP_URL）：
  python test/smoke_platforms_cdp.py
  python test/smoke_platforms_cdp.py --platforms chatgpt,deepseek
  python test/smoke_platforms_cdp.py --output docs/smoke_report.json

无 CDP 时仍可运行，结果全部为 skipped。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 将 src 加入 path，便于直接运行
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from oneqmultia.config.settings import Settings  # noqa: E402
from oneqmultia.core.dispatcher import dispatch_to_adapters  # noqa: E402
from oneqmultia.core.platform_registry import PlatformRegistry  # noqa: E402
from oneqmultia.platform_manager.seed import seed_platforms_if_empty  # noqa: E402
from oneqmultia.storage import init_db  # noqa: E402
from oneqmultia.storage.database import SessionLocal  # noqa: E402


async def _connect_cdp(cdp_url: str):
    """连接 CDP 浏览器，失败返回 None。"""
    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        return pw, browser, ctx
    except Exception as e:
        print(f"CDP 连接失败: {e}", file=sys.stderr)
        return None, None, None


async def run_smoke(
    platform_filter: list[str] | None,
    question: str,
) -> dict:
    """执行冒烟测试并返回报告字典。"""
    init_db()
    db = SessionLocal()
    try:
        seed_platforms_if_empty(db)
        registry = PlatformRegistry(db)
        adapters = registry.get_enabled_adapters()
        if platform_filter:
            wanted = set(platform_filter)
            adapters = [a for a in adapters if a.platform_id in wanted]

        settings = Settings()
        pw, browser, ctx = (None, None, None)
        if settings.cdp_url:
            pw, browser, ctx = await _connect_cdp(settings.cdp_url)

        results = await dispatch_to_adapters(
            adapters,
            question,
            ctx,
        )

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cdp_url": settings.cdp_url,
            "cdp_connected": ctx is not None,
            "question": question,
            "total": len(results),
            "summary": {
                "success": sum(1 for r in results if r.status == "success"),
                "skipped": sum(1 for r in results if r.status == "skipped"),
                "error": sum(1 for r in results if r.status == "error"),
                "timeout": sum(1 for r in results if r.status == "timeout"),
            },
            "platforms": [
                {
                    "platform_id": r.platform_id,
                    "platform_name": r.platform_name,
                    "status": r.status,
                    "duration_ms": r.response_duration_ms,
                    "error_message": r.error_message or "",
                    "answer_preview": (r.answer_text or "")[:200],
                }
                for r in results
            ],
        }
        return report
    finally:
        db.close()
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        if pw is not None:
            await pw.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="OneQMultiA 平台 CDP 冒烟测试")
    parser.add_argument(
        "--platforms",
        type=str,
        default="",
        help="逗号分隔的平台 id，默认全部启用平台",
    )
    parser.add_argument(
        "--question",
        type=str,
        default="请用一句话介绍你自己。",
        help="测试问题",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="报告输出 JSON 路径（可选）",
    )
    args = parser.parse_args()
    pf = [x.strip() for x in args.platforms.split(",") if x.strip()] or None

    report = asyncio.run(run_smoke(pf, args.question))

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"\n报告已写入: {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
