"""RS vs SPY — 20日超额收益=个股收益-SPY收益。"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class RelativeStrengthIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="RS vs SPY",
            category="spot",
            max_score=2,
            participates_in_voting=True,
            description="20日超额收益=个股收益-SPY收益。",
        )

    def dependencies(self) -> List[str]:
        return ["spot_close"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        close: pd.Series = context.get("spot_close", pd.Series(dtype=float))
        benchmark_close = bundle.benchmark_history["Close"].dropna()

        if len(close) < 21 or len(benchmark_close) < 21:
            return IndicatorResult(
                name="RS vs SPY",
                raw_value=None,
                score=0,
                signal="中性",
                explain="股票或SPY历史不足21个交易日。",
                available=False,
            )

        stock_ret20 = float(close.iloc[-1] / close.iloc[-21] - 1)
        spy_ret20 = float(benchmark_close.iloc[-1] / benchmark_close.iloc[-21] - 1)
        rs = stock_ret20 - spy_ret20

        if rs > 0.10:
            score = 2
        elif rs > 0.05:
            score = 1
        else:
            score = 0

        if rs > 0:
            signal = "看涨"
        elif rs < 0:
            signal = "看跌"
        else:
            signal = "中性"

        return IndicatorResult(
            name="RS vs SPY",
            raw_value={
                "stock_ret20": round(stock_ret20, 4),
                "spy_ret20": round(spy_ret20, 4),
                "rs": round(rs, 4),
            },
            score=score,
            signal=signal,
            explain="20日超额收益=个股收益-SPY收益。",
        )
