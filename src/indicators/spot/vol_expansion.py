"""波动率扩张 — 短期HV(10d)大于长期HV(50d)记1分。"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..base import BaseIndicator, IndicatorMeta
from ...config import TRADING_DAYS_PER_YEAR
from ...models import IndicatorResult, MarketDataBundle


class VolExpansionIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="波动率扩张",
            category="spot",
            max_score=1,
            participates_in_voting=True,
            description="短期HV(10d)大于长期HV(50d)记1分。",
        )

    def dependencies(self) -> List[str]:
        return ["spot_close", "daily_return"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        close: pd.Series = context.get("spot_close", pd.Series(dtype=float))
        daily_return = context.get("daily_return", np.nan)

        returns = close.pct_change().dropna()
        if len(returns) < 50:
            return IndicatorResult(
                name="波动率扩张",
                raw_value=None,
                score=0,
                signal="中性",
                explain="收益率历史不足50个交易日。",
                available=False,
            )

        hv10 = float(returns.tail(10).std() * math.sqrt(TRADING_DAYS_PER_YEAR))
        hv50 = float(returns.tail(50).std() * math.sqrt(TRADING_DAYS_PER_YEAR))
        expansion = hv10 > hv50

        if expansion and np.isfinite(daily_return) and daily_return > 0:
            signal = "看涨"
        elif expansion and np.isfinite(daily_return) and daily_return < 0:
            signal = "看跌"
        else:
            signal = "中性"

        return IndicatorResult(
            name="波动率扩张",
            raw_value={"hv10": round(hv10, 4), "hv50": round(hv50, 4)},
            score=1 if expansion else 0,
            signal=signal,
            explain="短期HV(10d)大于长期HV(50d)记1分。",
        )
