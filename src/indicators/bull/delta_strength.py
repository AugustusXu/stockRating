"""② Delta 方向强度 — >=5000=4分, >=2000=3分, >=500=2分, >0=1分。"""

from __future__ import annotations

from typing import Any, Dict

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class DeltaStrengthDimension(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="Delta方向强度",
            category="bull",
            max_score=4,
            participates_in_voting=False,
            description="净Delta越大，方向确定性越高。",
        )

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        net_delta = context.get("net_delta")
        if net_delta is None:
            return IndicatorResult(
                name="Delta方向强度",
                raw_value=None,
                score=0,
                signal="不可用",
                explain="净Delta数据缺失。",
                available=False,
            )

        if net_delta >= 5000:
            score, signal = 4, "极强"
        elif net_delta >= 2000:
            score, signal = 3, "强"
        elif net_delta >= 500:
            score, signal = 2, "中"
        elif net_delta > 0:
            score, signal = 1, "轻度"
        else:
            score, signal = 0, "不满足"

        return IndicatorResult(
            name="Delta方向强度",
            raw_value=round(net_delta, 2),
            score=score,
            signal=signal,
            explain="聪明钱通过期权押注正股上涨的力度。",
        )
