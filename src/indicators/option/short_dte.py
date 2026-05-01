"""末日期权效应 — 最活跃合约DTE<=5则加分。"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class ShortDteIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="末日期权效应",
            category="option",
            max_score=2,
            participates_in_voting=False,
            description="最活跃合约DTE<=5则加分。",
        )

    def dependencies(self) -> List[str]:
        return ["option_frame"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        option_frame: pd.DataFrame = context.get("option_frame", pd.DataFrame())
        if option_frame.empty:
            return IndicatorResult(
                name="末日期权效应",
                raw_value=None,
                score=0,
                signal="中性",
                explain="期权链数据为空，无法计算该指标。",
                available=False,
            )

        if float(option_frame["volume"].sum()) > 0:
            active_row = option_frame.sort_values("volume", ascending=False).iloc[0]
            active_dte = int(active_row["dte"])
        else:
            active_dte = int(option_frame["dte"].min())

        score = 2 if active_dte <= 5 else 0

        return IndicatorResult(
            name="末日期权效应",
            raw_value=int(active_dte),
            score=score,
            signal="近到期" if score > 0 else "常规",
            explain="最活跃合约DTE<=5则加分。",
        )
