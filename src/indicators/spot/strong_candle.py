"""强阳柱 — 当日涨幅>5%记1分。"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class StrongCandleIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="强阳柱",
            category="spot",
            max_score=1,
            participates_in_voting=True,
            description="当日涨幅>5%记1分。",
        )

    def dependencies(self) -> List[str]:
        return ["daily_return"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        daily_return = context.get("daily_return", np.nan)

        score = 1 if np.isfinite(daily_return) and daily_return > 0.05 else 0

        if np.isfinite(daily_return) and daily_return > 0.05:
            signal = "看涨"
        elif np.isfinite(daily_return) and daily_return < -0.05:
            signal = "看跌"
        else:
            signal = "中性"

        return IndicatorResult(
            name="强阳柱",
            raw_value=round(float(daily_return), 4) if np.isfinite(daily_return) else None,
            score=score,
            signal=signal,
            explain="当日涨幅>5%记1分。",
        )
