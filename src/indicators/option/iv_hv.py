"""IV/HV比率 — ATM IV 与 20日历史波动率的比值。"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class IvHvIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="IV/HV比率",
            category="option",
            max_score=3,
            participates_in_voting=False,
            description="ATM IV与20日历史波动率比值。",
        )

    def dependencies(self) -> List[str]:
        return ["atm_iv", "hv20"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        atm_iv = context.get("atm_iv", np.nan)
        hv20 = context.get("hv20", np.nan)

        ratio = (
            float(atm_iv / hv20)
            if np.isfinite(atm_iv) and np.isfinite(hv20) and hv20 > 0
            else np.nan
        )

        if not np.isfinite(ratio):
            return IndicatorResult(
                name="IV/HV比率",
                raw_value={
                    "atm_iv": round(float(atm_iv), 4) if np.isfinite(atm_iv) else None,
                    "hv20": round(float(hv20), 4) if np.isfinite(hv20) else None,
                    "iv_hv": None,
                },
                score=0,
                signal="中性",
                explain="ATM IV或HV不足，IV/HV不可计算。",
                available=False,
            )

        if ratio > 2.0:
            score, signal = 3, "波动溢价高"
        elif ratio > 1.5:
            score, signal = 2, "波动偏贵"
        elif ratio < 0.5:
            score, signal = 3, "波动极低估"
        elif ratio < 0.7:
            score, signal = 2, "波动低估"
        else:
            score, signal = 0, "中性"

        return IndicatorResult(
            name="IV/HV比率",
            raw_value={
                "atm_iv": round(float(atm_iv), 4) if np.isfinite(atm_iv) else None,
                "hv20": round(float(hv20), 4) if np.isfinite(hv20) else None,
                "iv_hv": round(float(ratio), 4),
            },
            score=score,
            signal=signal,
            explain="ATM IV与20日历史波动率比值。",
        )
