"""最优答案合成：共识合并、单源回退、噪声过滤。"""

from oneqmultia.core.compare import compare_answers, synthesize_optimal_answer


def _ans(pid: str, name: str, text: str, status: str = "success", ms: int = 1200) -> dict:
    return {
        "platform_id": pid,
        "platform_name": name,
        "answer_text": text,
        "status": status,
        "response_duration_ms": ms,
    }


def test_optimal_merges_consensus_and_unique_points() -> None:
    answers = [
        _ans(
            "a",
            "助手A",
            "智能体是能自主感知环境并采取行动的系统。它通常包含规划、记忆和工具调用。生命科学智能体还需要连接实验数据。",
        ),
        _ans(
            "b",
            "助手B",
            "智能体是能自主感知环境并采取行动的系统。构建生命科学智能体时，应接入文献库与组学数据。",
            ms=2400,
        ),
        _ans("c", "助手C", "", status="error", ms=0),
    ]
    result = compare_answers(answers)
    opt = result["optimal_answer"]
    assert result["compared_count"] == 2
    assert "智能体" in opt["text"]
    assert len(opt["sources"]) == 2
    assert opt["recommended_source"]["platform_id"] in {"a", "b"}
    assert opt["confidence"] > 0.5
    assert any("智能体" in p["text"] for p in opt["key_points"])


def test_optimal_single_success_keeps_original() -> None:
    text = "智能体是能够感知环境、制定计划并调用工具完成任务的软件系统。"
    opt = synthesize_optimal_answer([_ans("only", "唯一助手", text)])
    assert opt["text"] == text
    assert opt["recommended_source"]["platform_name"] == "唯一助手"
    assert opt["confidence"] < 0.6


def test_optimal_filters_scrape_noise() -> None:
    opt = synthesize_optimal_answer(
        [
            _ans("x", "失败页", "未检测到回答文本（响应区域为空或选择器不匹配）"),
            _ans("y", "空", "短"),
        ]
    )
    assert opt["text"] == ""
    assert opt["sources"] == []


def test_optimal_empty_answers() -> None:
    result = compare_answers([])
    assert result["compared_count"] == 0
    assert result["optimal_answer"]["text"] == ""
