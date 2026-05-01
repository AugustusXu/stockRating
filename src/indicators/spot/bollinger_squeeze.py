"""布林带压缩 — 布林带宽度=(Upper-Lower)/Middle，阈值取3%。"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class BollingerSqueezeIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="布林带压缩",
            category="spot",
            max_score=1,
            participates_in_voting=False,
            description="布林带宽度=(Upper-Lower)/Middle，阈值取3%。",
        )

    def dependencies(self) -> List[str]:
        return ["spot_close"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        close: pd.Series = context.get("spot_close", pd.Series(dtype=float))

        if len(close) < 20:
            return IndicatorResult(
                name="布林带压缩",
                raw_value=None,
                score=0,
                signal="中性",
                explain="收盘价历史不足20个交易日。",
                available=False,
            )

        rolling_mean = close.rolling(20).mean().iloc[-1]
        rolling_std = close.rolling(20).std().iloc[-1]

        if (
            not np.isfinite(rolling_mean)
            or rolling_mean <= 0
            or not np.isfinite(rolling_std)
        ):
            return IndicatorResult(
                name="布林带压缩",
                raw_value=None,
                score=0,
                signal="中性",
                explain="布林带计算失败。",
                available=False,
            )

        width = float((4 * rolling_std) / rolling_mean)
        is_squeeze = width < 0.03

        return IndicatorResult(
            name="布林带压缩",
            raw_value=round(width, 4),
            score=1 if is_squeeze else 0,
            signal="蓄力" if is_squeeze else "中性",
            explain="布林带宽度=(Upper-Lower)/Middle，阈值取3%。",
        )
