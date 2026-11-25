"""把多平台回答整理成共识、分歧和五维评分。"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

_SENTENCE = re.compile(r"[^。！？!?\n]+[。！？!?]?")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def build_consensus_matrix(answers: Iterable[dict[str, Any]]) -> Dict[str, Any]:
    """
    answers 项需要 platform_name、answer_text，可选 response_duration_ms。

    共识：至少两个平台都出现的句子。
    分歧：同一句话里数字不一致。
    评分：按长度、结构、速度给一个 0-100 的粗分，供界面展示，不是模型裁判。
    """
    usable = [item for item in answers if (item.get("answer_text") or "").strip() and item.get("status", "success") == "success"]
    sentence_owners: dict[str, list[str]] = {}
    for item in usable:
        name = item.get("platform_name") or item.get("platform_id") or "未知"
        seen: set[str] = set()
        for raw in _SENTENCE.findall(item.get("answer_text") or ""):
            sentence = " ".join(raw.split())
            if len(sentence) < 8 or sentence in seen:
                continue
            seen.add(sentence)
            sentence_owners.setdefault(sentence, []).append(str(name))

    agreements = [
        {"text": text, "sources": owners}
        for text, owners in sentence_owners.items()
        if len(owners) >= 2
    ]
    conflicts = _number_conflicts(usable)
    scores = [_score(item) for item in usable]
    return {
        "agreements": agreements[:12],
        "conflicts": conflicts[:12],
        "scores": scores,
    }


def _number_conflicts(answers: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """找出不同平台给出的不同数字。"""
    found: dict[str, set[str]] = {}
    for item in answers:
        name = str(item.get("platform_name") or "")
        numbers = set(_NUMBER.findall(item.get("answer_text") or ""))
        if name and numbers:
            found[name] = numbers
    names = list(found)
    conflicts: List[dict[str, Any]] = []
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            only_left = sorted(found[left] - found[right])
            only_right = sorted(found[right] - found[left])
            if only_left and only_right:
                conflicts.append({
                    "left": left,
                    "right": right,
                    "left_numbers": only_left[:6],
                    "right_numbers": only_right[:6],
                })
    return conflicts


def _score(item: dict[str, Any]) -> dict[str, Any]:
    text = item.get("answer_text") or ""
    length_score = min(100, int(len(text) / 8))
    structure = 40
    if "##" in text or "\n- " in text or "```" in text:
        structure = 85
    duration = item.get("response_duration_ms")
    if isinstance(duration, int) and duration > 0:
        speed = max(20, min(100, int(20000 / duration)))
    else:
        speed = 50
    overall = int(length_score * 0.4 + structure * 0.4 + speed * 0.2)
    return {
        "platform_name": item.get("platform_name") or "",
        "overall": overall,
        "length": length_score,
        "structure": structure,
        "speed": speed,
    }
