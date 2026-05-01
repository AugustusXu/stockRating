"""⑨ 波动率状态 — 波动率扩张=1分, 布林带压缩=1分（可叠加）。"""

from __future__ import annotations

from typing import Any, Dict

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class VolatilityStateDimension(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="波动率状态(看涨)",
            category="bull",
            max_score=2,
            participates_in_voting=False,
            description="波动率扩张+布林带压缩可叠加。",
        )

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        vol_expansion_score = context.get("vol_expansion_score", 0)
        bollinger_score = context.get("bollinger_score", 0)

        score = vol_expansion_score + bollinger_score

        parts = []
        if vol_expansion_score > 0:
            parts.append("波动率扩张")
        if bollinger_score > 0:
            parts.append("布林带压缩")

        signal = "+".join(parts) if parts else "平静"

        return IndicatorResult(
            name="波动率状态(看涨)",
            raw_value={
                "vol_expansion": bool(vol_expansion_score),
                "bollinger_squeeze": bool(bollinger_score),
            },
            score=score,
            signal=signal,
            explain="扩张=趋势加速, 压缩=突破前蓄力。",
        )
