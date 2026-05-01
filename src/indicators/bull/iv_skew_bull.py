"""④ IV Skew 反转（看涨筛选视角） — >1.0=4分, >0.1=3分, >0=2分。"""

from __future__ import annotations

from typing import Any, Dict

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class IvSkewBullDimension(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="IV Skew反转(看涨)",
            category="bull",
            max_score=4,
            participates_in_voting=False,
            description="Call IV > Put IV 说明有人不惜溢价买涨。",
        )

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        iv_skew = context.get("iv_skew")
        if iv_skew is None:
            return IndicatorResult(
                name="IV Skew反转(看涨)",
                raw_value=None,
                score=0,
                signal="不可用",
                explain="IV Skew数据缺失。",
                available=False,
            )

        if iv_skew > 1.0:
            score, signal = 4, "极端反转"
        elif iv_skew > 0.1:
            score, signal = 3, "显著反转"
        elif iv_skew > 0:
            score, signal = 2, "轻微反转"
        else:
            score, signal = 0, "未反转"

        return IndicatorResult(
            name="IV Skew反转(看涨)",
            raw_value=round(iv_skew, 4),
            score=score,
            signal=signal,
            explain="Call比Put贵=最难伪造的看涨信号。",
        )
