"""最优答案 LLM 合成：配置解析、重写成功、失败回退。"""

from oneqmultia.config.settings import Settings
from oneqmultia.core.compare import compare_answers
from oneqmultia.core.llm_catalog import public_catalog
from oneqmultia.core.llm_synthesizer import (
    llm_public_status,
    resolve_llm_endpoint,
    synthesize_with_llm,
)


def _answers() -> list[dict]:
    return [
        {
            "platform_id": "a",
            "platform_name": "助手A",
            "status": "success",
            "answer_text": "个人站点可以用 GitHub Pages 托管静态页，成本最低。",
            "response_duration_ms": 1000,
        },
        {
            "platform_id": "b",
            "platform_name": "助手B",
            "status": "success",
            "answer_text": "若要更像作品集，可用 Astro 或 Next.js 生成站点并绑定自定义域名。",
            "response_duration_ms": 1500,
        },
    ]


def test_resolve_prefers_deepseek(monkeypatch) -> None:
    monkeypatch.setenv("ONEQMULTIA_DEEPSEEK_API_KEY", "sk-ds")
    monkeypatch.setenv("ONEQMULTIA_KIMI_API_KEY", "sk-kimi")
    monkeypatch.setenv("ONEQMULTIA_LLM_PROVIDER", "auto")
    ep = resolve_llm_endpoint(Settings())
    assert ep is not None
    assert ep.provider == "deepseek"
    assert ep.model == "deepseek-v4-flash"
    assert llm_public_status(Settings())["configured"] is True
    assert "sk-ds" not in str(llm_public_status(Settings()))


def test_resolve_kimi_when_chosen(monkeypatch) -> None:
    monkeypatch.setenv("ONEQMULTIA_KIMI_API_KEY", "sk-kimi")
    monkeypatch.setenv("ONEQMULTIA_DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("ONEQMULTIA_LLM_PROVIDER", "kimi")
    ep = resolve_llm_endpoint(Settings())
    assert ep is not None
    assert ep.provider == "kimi"
    assert "moonshot" in ep.base_url


def test_llm_rewrite_replaces_snippet_merge(monkeypatch) -> None:
    monkeypatch.setenv("ONEQMULTIA_DEEPSEEK_API_KEY", "sk-ds")
    monkeypatch.setenv("ONEQMULTIA_LLM_PROVIDER", "deepseek")

    def fake_chat(endpoint, system, user):
        assert "GitHub Pages" in user
        assert endpoint.provider == "deepseek"
        return '{"text":"建议先用 GitHub Pages 上线，再用 Astro 做成作品集并绑定域名。","summary":"静态托管加作品集框架","key_points":[{"text":"先上线再打磨","sources":["助手A","助手B"]}]}'

    monkeypatch.setattr("oneqmultia.core.llm_synthesizer._chat_complete", fake_chat)
    result = compare_answers(_answers(), question="怎么做个人网站？", use_llm=True)
    opt = result["optimal_answer"]
    assert opt["method"] == "llm"
    assert "Astro" in opt["text"]
    assert "共识要点" not in opt["text"]
    assert opt["provider_label"] == "DeepSeek"


def test_llm_failure_falls_back_to_local(monkeypatch) -> None:
    monkeypatch.setenv("ONEQMULTIA_DEEPSEEK_API_KEY", "sk-ds")
    monkeypatch.setenv("ONEQMULTIA_LLM_PROVIDER", "deepseek")

    def boom(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("oneqmultia.core.llm_synthesizer._chat_complete", boom)
    result = compare_answers(_answers(), question="怎么做个人网站？", use_llm=True)
    assert result["optimal_answer"]["method"] == "consensus_merge"
    assert result["optimal_answer"]["text"]


def test_synthesize_without_key_returns_none() -> None:
    heuristic = {"text": "x", "confidence": 0.4}
    assert synthesize_with_llm("q", _answers(), heuristic) is None


def test_catalog_includes_domestic_vendors() -> None:
    ids = {item["id"] for item in public_catalog()["providers"]}
    assert {"minimax", "glm", "longcat", "qwen", "doubao", "mimo"} <= ids


def test_resolve_qwen_glm_minimax(monkeypatch) -> None:
    monkeypatch.setenv("ONEQMULTIA_QWEN_API_KEY", "sk-qwen")
    monkeypatch.setenv("ONEQMULTIA_GLM_API_KEY", "sk-glm")
    monkeypatch.setenv("ONEQMULTIA_MINIMAX_API_KEY", "sk-mm")
    qwen = resolve_llm_endpoint(Settings(), provider="qwen", model="qwen3.7-plus")
    assert qwen is not None
    assert "dashscope" in qwen.base_url
    assert qwen.model == "qwen3.7-plus"
    glm = resolve_llm_endpoint(Settings(), provider="glm", model="glm-4.7")
    assert glm is not None and glm.model == "glm-4.7"
    mm = resolve_llm_endpoint(Settings(), provider="minimax", model="MiniMax-M3")
    assert mm is not None and mm.model == "MiniMax-M3"


def test_compare_uses_requested_model(monkeypatch) -> None:
    monkeypatch.setenv("ONEQMULTIA_GLM_API_KEY", "sk-glm")

    def fake_chat(endpoint, system, user):
        assert endpoint.provider == "glm"
        assert endpoint.model == "glm-5.2"
        return '{"text":"这是用 GLM-5.2 重写的完整个人站点方案，包含托管与框架选择。","summary":"GLM 重写","key_points":[]}'

    monkeypatch.setattr("oneqmultia.core.llm_synthesizer._chat_complete", fake_chat)
    result = compare_answers(
        _answers(),
        question="怎么做个人网站？",
        use_llm=True,
        llm_provider="glm",
        llm_model="glm-5.2",
    )
    assert result["optimal_answer"]["model"] == "glm-5.2"
    assert result["optimal_answer"]["provider"] == "glm"
