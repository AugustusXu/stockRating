"""P/C Ratio — 看跌/看涨成交量比率。"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class PcRatioIndicator(BaseIndicator):

    DEFAULT_THRESHOLDS = {
        "strong_bull": 0.3,
        "mild_bull": 0.5,
        "mild_bear": 2.0,
        "strong_bear": 3.0,
    }

    def __init__(self, thresholds: dict | None = None) -> None:
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="P/C Ratio",
            category="option",
            max_score=3,
            participates_in_voting=True,
            description="按看跌成交量/看涨成交量分档。",
        )

    def dependencies(self) -> List[str]:
        return ["option_frame"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        option_frame: pd.DataFrame = context.get("option_frame", pd.DataFrame())
        if option_frame.empty:
            return IndicatorResult(
                name="P/C Ratio",
                raw_value=None,
                score=0,
                signal="中性",
                explain="期权链数据为空，无法计算该指标。",
                available=False,
            )

        total_call_volume = float(
            option_frame.loc[option_frame["optionType"] == "call", "volume"].sum()
        )
        total_put_volume = float(
            option_frame.loc[option_frame["optionType"] == "put", "volume"].sum()
        )
        pc_ratio = (
            total_put_volume / total_call_volume if total_call_volume > 0 else np.nan
        )

        if not np.isfinite(pc_ratio):
            return IndicatorResult(
                name="P/C Ratio",
                raw_value=None,
                score=0,
                signal="中性",
                explain="缺少有效看涨成交量，P/C不可计算。",
                available=False,
            )

        t = self.thresholds
        if pc_ratio < t["strong_bull"]:
            score, signal = 3, "强看涨"
        elif pc_ratio < t["mild_bull"]:
            score, signal = 1, "偏看涨"
        elif pc_ratio > t["strong_bear"]:
            score, signal = 3, "强看跌"
        elif pc_ratio > t["mild_bear"]:
            score, signal = 1, "偏看跌"
        else:
            score, signal = 0, "中性"

        return IndicatorResult(
            name="P/C Ratio",
            raw_value=round(pc_ratio, 4),
            score=score,
            signal=signal,
            explain="按看跌成交量/看涨成交量分档。",
        )
