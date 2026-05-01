"""Vol/OI极端 — 最大成交量/持仓量比值分档打分。"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class VolOiIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="Vol/OI极端",
            category="option",
            max_score=5,
            participates_in_voting=False,
            description="按最大成交量/持仓量比值分档打分。",
        )

    def dependencies(self) -> List[str]:
        return ["option_frame"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        option_frame: pd.DataFrame = context.get("option_frame", pd.DataFrame())
        if option_frame.empty:
            return IndicatorResult(
                name="Vol/OI极端",
                raw_value=None,
                score=0,
                signal="中性",
                explain="期权链数据为空，无法计算该指标。",
                available=False,
            )

        valid_voi = option_frame[
            (option_frame["volume"] > 0) & (option_frame["openInterest"] > 0)
        ].copy()

        if valid_voi.empty:
            return IndicatorResult(
                name="Vol/OI极端",
                raw_value=None,
                score=0,
                signal="中性",
                explain="缺少有效volume/openInterest组合。",
                available=False,
            )

        valid_voi["vol_oi_ratio"] = valid_voi["volume"] / valid_voi["openInterest"]
        max_voi_ratio = float(valid_voi["vol_oi_ratio"].max())

        # 联动行权价数量写入 context 供 MultiStrikeIndicator 使用
        context["linked_strike_count"] = int(
            valid_voi.loc[valid_voi["vol_oi_ratio"] >= 3, "strike"].nunique()
        )

        if not np.isfinite(max_voi_ratio):
            return IndicatorResult(
                name="Vol/OI极端",
                raw_value=None,
                score=0,
                signal="中性",
                explain="缺少有效volume/openInterest组合。",
                available=False,
            )

        if max_voi_ratio >= 10:
            score = 5
        elif max_voi_ratio >= 5:
            score = 3
        elif max_voi_ratio >= 3:
            score = 1
        else:
            score = 0

        return IndicatorResult(
            name="Vol/OI极端",
            raw_value=round(max_voi_ratio, 4),
            score=score,
            signal="异动" if score > 0 else "中性",
            explain="按最大成交量/持仓量比值分档打分。",
        )

    def provide(self) -> List[str]:
        return ["linked_strike_count"]
