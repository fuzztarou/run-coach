"""Garmin descriptionのパース。"""

from __future__ import annotations

import re

# RPE行のパターン（全角・半角コロン、全角・半角数字対応）
_RPE_PATTERN = re.compile(r"RPE\s*[:：]\s*([\d０-９]+)", re.IGNORECASE)
# 痛み行のパターン（英語 "Pain" / 日本語 "痛み" 両対応）
_PAIN_PATTERN = re.compile(r"(?:Pain|痛み)\s*[:：]\s*(.+)", re.IGNORECASE)
# コメント行のパターン（英語 "Comment" / 日本語 "コメント" 両対応）
_COMMENT_PATTERN = re.compile(r"(?:Comment|コメント)\s*[:：]\s*(.+)", re.IGNORECASE)


def parse_description(text: str | None) -> dict:
    """Garmin descriptionをパースして振り返り情報を抽出する。

    Returns:
        {"rpe": int|None, "pain": str|None, "comment": str|None}
    """
    if not text or not text.strip():
        return {"rpe": None, "pain": None, "comment": None}

    rpe = None
    pain = None
    comment = None

    rpe_match = _RPE_PATTERN.search(text)
    if rpe_match:
        raw = rpe_match.group(1)
        normalized = raw.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        rpe_value = int(normalized)
        if 1 <= rpe_value <= 10:
            rpe = rpe_value

    pain_match = _PAIN_PATTERN.search(text)
    if pain_match:
        pain_text = pain_match.group(1).strip()
        if pain_text:
            pain = pain_text

    comment_match = _COMMENT_PATTERN.search(text)
    if comment_match:
        comment_text = comment_match.group(1).strip()
        if comment_text:
            comment = comment_text
    elif not rpe_match and not pain_match:
        # RPE行も痛み行もなければ、全文をcommentとして扱う
        comment = text.strip()

    return {"rpe": rpe, "pain": pain, "comment": comment}
