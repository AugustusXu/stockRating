"""① γ Wall 突破位置 — 0~3%=4分, 3~8%=3分, 8~15%=1分。"""

from __future__ import annotations

from typing import Any, Dict, List

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class GammaWallBreakoutDimension(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="γ Wall突破位置",
            category="bull",
            max_score=4,
            participates_in_voting=False,
            description="刚突破0~3%=4分, 突破3~8%=3分, 突破8~15%=1分。",
        )

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        excess_pct: float = context.get("excess_pct", 0.0)

        if excess_pct <= 0.03:
            score, signal = 4, "最佳窗口"
        elif excess_pct <= 0.08:
            score, signal = 3, "趋势确认"
        elif excess_pct <= 0.15:
            score, signal = 1, "注意追高"
        else:
            score, signal = 0, "超出范围"

        return IndicatorResult(
            name="γ Wall突破位置",
            raw_value=round(excess_pct * 100, 2),
            score=score,
            signal=signal,
            explain=f"突破γ Wall {round(excess_pct * 100, 1)}%。",
        )
