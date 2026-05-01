"""⑤ 期现共振（看涨筛选视角） — 真共振=4分, 半共振=2分。"""

from __future__ import annotations

from typing import Any, Dict

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class ResonanceBullDimension(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="期现共振(看涨)",
            category="bull",
            max_score=4,
            participates_in_voting=False,
            description="期权与现货同时看涨=最高质量信号。",
        )

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        resonance_label = context.get("resonance_label", "")

        if resonance_label == "HOT":
            score, signal = 4, "真共振"
        elif resonance_label == "WARM":
            score, signal = 2, "半共振"
        else:
            score, signal = 0, "无共振"

        return IndicatorResult(
            name="期现共振(看涨)",
            raw_value=resonance_label or "无",
            score=score,
            signal=signal,
            explain="两个独立维度互相验证的方向一致性。",
        )
