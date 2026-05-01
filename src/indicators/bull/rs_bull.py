"""⑥ RS% 相对强度（看涨筛选视角） — >=20%=3分, >=10%=2分, >=0=1分。"""

from __future__ import annotations

from typing import Any, Dict

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class RsBullDimension(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="RS%相对强度(看涨)",
            category="bull",
            max_score=3,
            participates_in_voting=False,
            description="20天持续跑赢SPY=资金用脚投票。",
        )

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        rs = context.get("rs")
        if rs is None:
            return IndicatorResult(
                name="RS%相对强度(看涨)",
                raw_value=None,
                score=0,
                signal="不可用",
                explain="RS数据缺失。",
                available=False,
            )

        if rs >= 0.20:
            score, signal = 3, "极度强势"
        elif rs >= 0.10:
            score, signal = 2, "显著跑赢"
        elif rs >= 0:
            score, signal = 1, "跑赢大盘"
        else:
            score, signal = 0, "跑输大盘"

        return IndicatorResult(
            name="RS%相对强度(看涨)",
            raw_value=round(rs * 100, 2),
            score=score,
            signal=signal,
            explain="20日超额收益持续为正=资金偏好。",
        )
