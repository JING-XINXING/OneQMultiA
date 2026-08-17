"""答案对比分析，并整理多平台回答为最优解。"""

from __future__ import annotations

import difflib
import math
import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from oneqmultia.core.llm_synthesizer import synthesize_with_llm


# 页面抓取失败时偶发写入正文，合成时直接丢弃
_NOISE_MARKERS = (
    "未检测到回答",
    "找不到输入框",
    "选择器不匹配",
    "response_container",
    "selectors.input_box",
    "PATCH /api",
    "Thinking...",
    "思考中",
)

_HEADING_PREFIX = re.compile(r"^(#{1,6}\s+|[-*•●]\s+|\d+[\.、\)）]\s*)")
_SENT_SPLIT = re.compile(r"(?<=[。！？；])")


def _is_low_quality(text: str) -> bool:
    """过短或明显是抓取失败文案，不参与最优解。"""
    body = (text or "").strip()
    if len(body) < 24:
        return True
    return any(marker in body for marker in _NOISE_MARKERS)


def _char_ngram_sim(left: str, right: str, n: int = 2) -> float:
    """中文友好的字 bigram Jaccard，比 SequenceMatcher 更能识别同义改写。"""
    a = re.sub(r"\s+", "", left or "")
    b = re.sub(r"\s+", "", right or "")
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    def grams(s: str) -> set[str]:
        if len(s) < n:
            return {s}
        return {s[i : i + n] for i in range(len(s) - n + 1)}

    ga, gb = grams(a), grams(b)
    return len(ga & gb) / len(ga | gb)


def _split_points(text: str) -> List[str]:
    """按段落、列表和中文句号切出可合并的要点。"""
    points: List[str] = []
    for block in re.split(r"\n+", text or ""):
        cleaned = _HEADING_PREFIX.sub("", block.strip()).strip()
        if not cleaned:
            continue
        chunks = _SENT_SPLIT.split(cleaned) if re.search(r"[。！？；]", cleaned) else [cleaned]
        for chunk in chunks:
            item = re.sub(r"\s+", " ", chunk).strip()
            if len(item) >= 12:
                points.append(item)
    return points


def _structure_score(text: str) -> float:
    """结构完整度：列表、分段、论证连接词。"""
    score = 0.35
    if re.search(r"(?m)^(\d+[\.、]|[-*•]|#{1,3}\s)", text):
        score += 0.25
    if text.count("\n") >= 2:
        score += 0.15
    if any(token in text for token in ("首先", "其次", "此外", "总之", "例如", "包括", "步骤", "因此")):
        score += 0.15
    if "？" in text or "?" in text:
        score += 0.05
    return min(1.0, score)


def _length_score(n: int) -> float:
    """篇幅分：过短不完整，过长可能灌水，800–2200 字附近最高。"""
    if n < 40:
        return 0.12
    if n < 200:
        return 0.35 + n / 800
    if n <= 2200:
        return min(1.0, 0.72 + math.log10(n / 200) * 0.28)
    return max(0.62, 1.0 - (n - 2200) / 12000)


def _consensus_score(pid: str, pids: Sequence[str], texts: Dict[str, str]) -> float:
    """与其他成功回答的平均相似度；仅一条时给中性分。"""
    others = [other for other in pids if other != pid]
    if not others:
        return 0.5
    sims = [_char_ngram_sim(texts[pid], texts[other]) for other in others]
    return sum(sims) / len(sims)


def _score_answer(text: str, consensus: float) -> float:
    """综合完整度、共识度和结构，选出推荐原文来源。"""
    n = len((text or "").strip())
    return round(
        0.40 * _length_score(n) + 0.35 * consensus + 0.25 * _structure_score(text),
        4,
    )


def _cluster_points(
    items: Iterable[Tuple[str, str]],
    threshold: float = 0.42,
) -> List[Dict[str, Any]]:
    """把相近要点归并，代表句取更完整的一条。"""
    clusters: List[Dict[str, Any]] = []
    for text, source in items:
        placed = False
        for cluster in clusters:
            if _char_ngram_sim(text, cluster["text"]) >= threshold:
                cluster["sources"].add(source)
                if len(text) > len(cluster["text"]) * 1.08:
                    cluster["text"] = text
                placed = True
                break
        if not placed:
            clusters.append({"text": text, "sources": {source}})
    clusters.sort(key=lambda c: (-len(c["sources"]), -len(c["text"])))
    return clusters


def _build_optimal_text(
    consensus_points: List[Dict[str, Any]],
    extra_points: List[Dict[str, Any]],
    source_count: int,
    recommended_name: str,
) -> str:
    """把聚类结果整理成可读的最优解正文。"""
    lines: List[str] = [
        f"综合 {source_count} 个平台的成功回答，整理如下。",
        "",
        "共识要点",
    ]
    if consensus_points:
        for index, point in enumerate(consensus_points, start=1):
            lines.append(f"{index}. {point['text']}")
    else:
        lines.append("各平台表述差异较大，以下按完整度选取关键信息。")

    if extra_points:
        lines.extend(["", "补充视角"])
        for point in extra_points:
            names = "、".join(sorted(point["sources"]))
            lines.append(f"- {point['text']}（{names}）")

    if recommended_name:
        lines.extend(["", f"若需要单篇完整原文，建议优先阅读「{recommended_name}」。"])
    return "\n".join(lines).strip()


def synthesize_optimal_answer(success: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    不依赖外部大模型：筛成功回答 → 打分 → 要点聚类 → 拼出最优解。
    共识要点优先，独特补充单独列出，并标明推荐原文来源。
    """
    usable = [a for a in success if not _is_low_quality(str(a.get("answer_text") or ""))]
    empty = {
        "text": "",
        "summary": "",
        "key_points": [],
        "recommended_source": None,
        "sources": [],
        "method": "consensus_merge",
        "confidence": 0.0,
        "rationale": "暂无可用的成功回答，无法整理最优解。",
    }
    if not usable:
        return empty

    texts = {a["platform_id"]: str(a.get("answer_text") or "") for a in usable}
    names = {a["platform_id"]: a.get("platform_name", a["platform_id"]) for a in usable}
    pids = list(texts.keys())

    scored: List[Dict[str, Any]] = []
    for item in usable:
        pid = item["platform_id"]
        consensus = _consensus_score(pid, pids, texts)
        score = _score_answer(texts[pid], consensus)
        scored.append(
            {
                "platform_id": pid,
                "platform_name": names[pid],
                "score": score,
                "consensus": round(consensus, 4),
                "char_count": len(texts[pid]),
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    best = scored[0]

    paired: List[Tuple[str, str]] = []
    for item in usable:
        src = names[item["platform_id"]]
        for point in _split_points(texts[item["platform_id"]]):
            paired.append((point, src))

    clusters = _cluster_points(paired)
    consensus_pts = [c for c in clusters if len(c["sources"]) >= 2][:6]
    extra_pts = [c for c in clusters if len(c["sources"]) == 1][:4]
    if not consensus_pts:
        consensus_pts = clusters[:5]
        extra_pts = []

    key_points = [
        {
            "text": c["text"],
            "sources": sorted(c["sources"]),
            "consensus": round(len(c["sources"]) / max(1, len(usable)), 3),
        }
        for c in (consensus_pts + extra_pts)
    ]

    n = len(usable)
    shared = max((len(c["sources"]) for c in clusters), default=1)
    confidence = 0.42 if n == 1 else min(0.92, 0.55 + 0.08 * min(n, 4) + 0.12 * (shared / n))

    if n == 1:
        rationale = f"仅「{best['platform_name']}」给出有效回答，已按原文整理为最优解。"
        text = texts[best["platform_id"]].strip()
        summary = key_points[0]["text"] if key_points else text[:80]
    else:
        rationale = (
            f"对比 {n} 个有效回答后，按共识覆盖与结构完整度整理。"
            f"推荐原文来自「{best['platform_name']}」。"
        )
        text = _build_optimal_text(consensus_pts, extra_pts, n, best["platform_name"])
        summary = consensus_pts[0]["text"] if consensus_pts else f"已综合 {n} 个平台回答"

    return {
        "text": text,
        "summary": summary[:160],
        "key_points": key_points,
        "recommended_source": {
            "platform_id": best["platform_id"],
            "platform_name": best["platform_name"],
            "score": best["score"],
            "reason": "篇幅更完整，且与其他回答的共识更高" if n > 1 else "当前唯一有效回答",
        },
        "sources": scored,
        "method": "consensus_merge",
        "provider": None,
        "provider_label": None,
        "model": None,
        "confidence": round(confidence, 3),
        "rationale": rationale,
    }


def compare_answers(
    answers: List[Dict[str, Any]],
    *,
    question: str = "",
    use_llm: bool = True,
    llm_provider: str = "",
    llm_model: str = "",
) -> Dict[str, Any]:
    """
    对多平台回答做对比分析，并给出整理后的最优解。
    配置了 DeepSeek/Kimi 等 Key 时，用大模型重写完整答案；失败则回退本地整理。
    """
    success = [a for a in answers if a.get("status") == "success" and a.get("answer_text")]
    texts = {a["platform_id"]: a.get("answer_text", "") for a in success}
    names = {a["platform_id"]: a.get("platform_name", a["platform_id"]) for a in success}

    lengths = [
        {"platform_id": pid, "platform_name": names[pid], "char_count": len(t), "word_count": len(t.split())}
        for pid, t in texts.items()
    ]

    durations = sorted(
        [
            {
                "platform_id": a["platform_id"],
                "platform_name": a.get("platform_name", ""),
                "duration_ms": a.get("response_duration_ms"),
            }
            for a in success
            if a.get("response_duration_ms") is not None
        ],
        key=lambda x: x["duration_ms"] or 0,
    )

    pids = list(texts.keys())
    similarity_matrix: List[Dict[str, Any]] = []
    for i, pa in enumerate(pids):
        for pb in pids[i + 1 :]:
            ratio = _char_ngram_sim(texts[pa], texts[pb])
            similarity_matrix.append(
                {
                    "platform_a": names[pa],
                    "platform_b": names[pb],
                    "similarity": round(ratio, 4),
                }
            )
    similarity_matrix.sort(key=lambda x: x["similarity"], reverse=True)

    diff_highlights: List[Dict[str, Any]] = []
    if len(pids) >= 2:
        base = texts[pids[0]]
        for pid in pids[1:]:
            diff = list(
                difflib.unified_diff(
                    base.splitlines(),
                    texts[pid].splitlines(),
                    fromfile=names[pids[0]],
                    tofile=names[pid],
                    lineterm="",
                )
            )
            diff_highlights.append(
                {
                    "base_platform": names[pids[0]],
                    "compare_platform": names[pid],
                    "diff_lines": diff[:40],
                }
            )

    heuristic = synthesize_optimal_answer(success)
    optimal = heuristic
    if use_llm and success:
        rewritten = synthesize_with_llm(
            question,
            success,
            heuristic,
            provider=llm_provider or None,
            model=llm_model or None,
        )
        if rewritten and rewritten.get("text"):
            optimal = rewritten

    return {
        "compared_count": len(success),
        "lengths": lengths,
        "duration_ranking": durations,
        "similarity_matrix": similarity_matrix,
        "diff_highlights": diff_highlights,
        "optimal_answer": optimal,
    }


def cached_or_local_optimal(qa: Any) -> Dict[str, Any]:
    """导出用：优先已缓存的最优解，避免再次调用付费模型。"""
    cached = getattr(qa, "optimal_answer", None)
    if isinstance(cached, dict) and str(cached.get("text") or "").strip():
        return cached
    payload = answers_to_compare_payload(getattr(qa, "answers", []) or [])
    return compare_answers(payload, question=getattr(qa, "question", "") or "", use_llm=False).get(
        "optimal_answer"
    ) or {}


def answers_to_compare_payload(answers: Iterable[Any]) -> List[Dict[str, Any]]:
    """把 ORM 回答行转成 compare_answers 所需字典。"""
    payload: List[Dict[str, Any]] = []
    for item in answers:
        payload.append(
            {
                "platform_id": item.platform_id,
                "platform_name": item.platform_name,
                "answer_text": item.answer_text,
                "response_duration_ms": item.response_duration_ms,
                "status": item.status,
            }
        )
    return payload
