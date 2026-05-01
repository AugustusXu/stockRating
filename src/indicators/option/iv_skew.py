"""IV Skew反转 — Call IV - Put IV 的ATM偏斜指标。"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class IvSkewIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="IV Skew反转",
            category="option",
            max_score=3,
            participates_in_voting=True,
            description="使用近月ATM: Call IV - Put IV。",
        )

    def dependencies(self) -> List[str]:
        return ["call_iv", "put_iv"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        call_iv = context.get("call_iv", np.nan)
        put_iv = context.get("put_iv", np.nan)

        iv_skew = (
            float(call_iv - put_iv)
            if np.isfinite(call_iv) and np.isfinite(put_iv)
            else np.nan
        )

        if not np.isfinite(iv_skew):
            return IndicatorResult(
                name="IV Skew反转",
                raw_value=None,
                score=0,
                signal="中性",
                explain="无法定位前月ATM的Call/Put IV。",
                available=False,
            )

        score = 3 if iv_skew > 0 else 0
        if iv_skew > 0.1:
            signal = "看涨"
        elif iv_skew < -0.1:
            signal = "看跌"
        else:
            signal = "中性"

        return IndicatorResult(
            name="IV Skew反转",
            raw_value=round(iv_skew, 4),
            score=score,
            signal=signal,
            explain="使用近月ATM: Call IV - Put IV。",
        )
