from __future__ import annotations

from typing import Dict, Tuple

from .models import IndicatorResult


def sum_scores(indicators: Dict[str, IndicatorResult]) -> int:
    return int(sum(item.score for item in indicators.values() if item.available))


def classify_votes(bull_votes: int, bear_votes: int) -> str:
    if bull_votes == 0 and bear_votes == 0:
        return "中性"

    if bull_votes == bear_votes:
        return "多空博弈"

    if bull_votes > bear_votes:
        if bull_votes >= 3 and bear_votes == 0:
            return "强看涨"
        if bear_votes == 0:
            return "看涨"
        return "偏看涨(有分歧)"

    if bear_votes >= 3 and bull_votes == 0:
        return "强看跌"
    if bull_votes == 0:
        return "看跌"
    return "偏看跌(有分歧)"


def is_bullish(label: str) -> bool:
    return "看涨" in label and "看跌" not in label


def is_bearish(label: str) -> bool:
    return "看跌" in label and "看涨" not in label


def compute_resonance(
    option_score: int,
    spot_score: int,
    option_direction: str,
    spot_direction: str,
) -> Tuple[int, str, str]:
    if option_score < 3 or spot_score < 3:
        return 0, "", "期权分或现货分未达到共振阈值(>=3)。"

    if (is_bullish(option_direction) and is_bullish(spot_direction)) or (
        is_bearish(option_direction) and is_bearish(spot_direction)
    ):
        return 5, "HOT", "期权与现货方向一致且强度达标，触发真共振。"

    if option_direction in {"中性", "多空博弈"} or spot_direction in {
        "中性",
        "多空博弈",
    }:
        return 3, "WARM", "期权与现货都存在异动，但至少一侧方向不明确。"

    return 1, "方向矛盾", "期权与现货方向冲突，可能存在对冲。"


def merge_overall_direction(option_direction: str, spot_direction: str) -> str:
    if is_bullish(option_direction) and is_bullish(spot_direction):
        return "看涨共识"

    if is_bearish(option_direction) and is_bearish(spot_direction):
        return "看跌共识"

    if option_direction not in {"中性", "多空博弈"}:
        return f"以期权为主: {option_direction}"

    if spot_direction not in {"中性", "多空博弈"}:
        return f"以现货为主: {spot_direction}"

    if option_direction == "多空博弈" or spot_direction == "多空博弈":
        return "多空博弈"

    return "中性"
