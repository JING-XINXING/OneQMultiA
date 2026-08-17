"""各平台回答等待超时应按历史耗时分层，而不是统一 120s。"""

from oneqmultia.platform_manager.seed import load_yaml_platforms
from oneqmultia.platforms import generic as generic_mod


def test_timeouts_are_tiered_by_platform() -> None:
    items = {row["id"]: int(row["timeout_seconds"]) for row in load_yaml_platforms()}
    assert items["grok"] >= 240
    assert items["copilot"] >= 210
    assert items["qianwen"] >= 210
    assert items["chatgpt"] >= 180
    assert items["deepseek"] <= 120
    assert items["kimi"] <= 120
    assert items["coze"] >= 120
    assert items["pi"] >= 180
    assert len(set(items.values())) >= 5


def test_input_wait_is_shorter_than_generation() -> None:
    """找不到输入框应尽快失败，把 timeout_seconds 留给真正生成回答。"""
    assert generic_mod._INPUT_WAIT_MS <= 15000
    assert generic_mod._ACTION_MS <= 15000
