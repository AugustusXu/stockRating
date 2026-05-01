"""③ P/C Ratio（看涨筛选视角） — <0.2=4分, <0.3=3分, <0.5=2分, <0.8=1分。"""

from __future__ import annotations

from typing import Any, Dict

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class PcRatioBullDimension(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="P/C Ratio(看涨)",
            category="bull",
            max_score=4,
            participates_in_voting=False,
            description="P/C越低，看涨一致性越强。",
        )

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        pc_ratio = context.get("pc_ratio")
        if pc_ratio is None:
            return IndicatorResult(
                name="P/C Ratio(看涨)",
                raw_value=None,
                score=0,
                signal="不可用",
                explain="P/C Ratio数据缺失。",
                available=False,
            )

        if pc_ratio < 0.2:
            score, signal = 4, "极端看涨"
        elif pc_ratio < 0.3:
            score, signal = 3, "强看涨"
        elif pc_ratio < 0.5:
            score, signal = 2, "偏看涨"
        elif pc_ratio < 0.8:
            score, signal = 1, "中性偏看涨"
        else:
            score, signal = 0, "不满足"

        return IndicatorResult(
            name="P/C Ratio(看涨)",
            raw_value=round(pc_ratio, 4),
            score=score,
            signal=signal,
            explain="看涨期权主导程度越强，方向预期越一致。",
        )
