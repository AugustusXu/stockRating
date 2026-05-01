"""⑦ IV/HV 波动定价（看涨筛选视角） — >2.0=2分, >1.5=1分。"""

from __future__ import annotations

from typing import Any, Dict

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class IvHvBullDimension(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="IV/HV波动定价(看涨)",
            category="bull",
            max_score=2,
            participates_in_voting=False,
            description="方向已确认看涨时，高IV/HV=市场预期大波动向上。",
        )

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        iv_hv_ratio = context.get("iv_hv_ratio")
        if iv_hv_ratio is None:
            return IndicatorResult(
                name="IV/HV波动定价(看涨)",
                raw_value=None,
                score=0,
                signal="不可用",
                explain="IV/HV数据缺失。",
                available=False,
            )

        if iv_hv_ratio > 2.0:
            score, signal = 2, "高波动定价"
        elif iv_hv_ratio > 1.5:
            score, signal = 1, "偏高定价"
        else:
            score, signal = 0, "正常"

        return IndicatorResult(
            name="IV/HV波动定价(看涨)",
            raw_value=round(iv_hv_ratio, 4),
            score=score,
            signal=signal,
            explain="方向确认后，高IV/HV=大波动+方向向上。",
        )
