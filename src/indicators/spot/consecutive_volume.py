"""连续放量>=3天 — 最近3天成交量均高于各自20日均量的1.3倍。"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class ConsecutiveVolumeIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="连续放量>=3天",
            category="spot",
            max_score=1,
            participates_in_voting=True,
            description="最近3天成交量均高于各自20日均量的1.3倍。",
        )

    def dependencies(self) -> List[str]:
        return ["spot_volume", "daily_return"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        volume: pd.Series = context.get("spot_volume", pd.Series(dtype=float))
        daily_return = context.get("daily_return", np.nan)

        if len(volume) < 23:
            return IndicatorResult(
                name="连续放量>=3天",
                raw_value=None,
                score=0,
                signal="中性",
                explain="成交量历史不足23个交易日。",
                available=False,
            )

        rolling20 = volume.rolling(20).mean()
        condition = (volume > rolling20 * 1.3).fillna(False)
        three_day_burst = bool(condition.tail(3).all())

        if three_day_burst and np.isfinite(daily_return) and daily_return > 0:
            signal = "看涨"
        elif three_day_burst and np.isfinite(daily_return) and daily_return < 0:
            signal = "看跌"
        else:
            signal = "中性"

        return IndicatorResult(
            name="连续放量>=3天",
            raw_value=bool(three_day_burst),
            score=1 if three_day_burst else 0,
            signal=signal,
            explain="最近3天成交量均高于各自20日均量的1.3倍。",
        )
