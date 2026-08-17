"""答案聚合：统计与简单结构化视图。"""

from typing import Any, Dict, List

from oneqmultia.platforms.base import AskResult


def summarize_results(results: List[AskResult]) -> Dict[str, Any]:
    """对一轮多平台结果做汇总，供 API / UI 使用。"""
    total = len(results)
    success = sum(1 for r in results if r.status == "success")
    skipped = sum(1 for r in results if r.status == "skipped")
    errors = sum(1 for r in results if r.status == "error")
    timeouts = sum(1 for r in results if r.status == "timeout")
    cancelled = sum(1 for r in results if r.status == "cancelled")
    durations = [r.response_duration_ms for r in results if r.response_duration_ms is not None]
    return {
        "total": total,
        "success": success,
        "skipped": skipped,
        "error": errors,
        "timeout": timeouts,
        "cancelled": cancelled,
        "avg_duration_ms": int(sum(durations) / len(durations)) if durations else None,
    }
