"""高位放量 — 收盘位于近252日高点75%以上，且5日均量>=20日均量1.5倍。"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class HighVolumeIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="高位放量",
            category="spot",
            max_score=3,
            participates_in_voting=True,
            description="收盘位于近252日高点75%以上，且5日均量>=20日均量1.5倍。",
        )

    def dependencies(self) -> List[str]:
        return ["spot_close", "spot_volume", "high_252"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        close: pd.Series = context.get("spot_close", pd.Series(dtype=float))
        volume: pd.Series = context.get("spot_volume", pd.Series(dtype=float))
        high_252: float = context.get("high_252", np.nan)

        if len(close) < 2:
            return IndicatorResult(
                name="高位放量",
                raw_value=None,
                score=0,
                signal="中性",
                explain="现货历史数据不足，无法计算。",
                available=False,
            )

        latest_close = float(close.iloc[-1])
        vol5 = float(volume.tail(5).mean())
        vol20 = float(volume.tail(20).mean()) if len(volume) >= 20 else np.nan
        vol_ratio = vol5 / vol20 if np.isfinite(vol20) and vol20 > 0 else np.nan
        close_to_high = latest_close / high_252 if high_252 > 0 else np.nan

        high_volume_at_high = bool(
            np.isfinite(vol_ratio)
            and vol_ratio >= 1.5
            and np.isfinite(close_to_high)
            and close_to_high >= 0.75
        )

        return IndicatorResult(
            name="高位放量",
            raw_value={
                "close_to_252h": round(close_to_high, 4) if np.isfinite(close_to_high) else None,
                "vol_5d_20d": round(vol_ratio, 4) if np.isfinite(vol_ratio) else None,
            },
            score=3 if high_volume_at_high else 0,
            signal="看涨" if high_volume_at_high else "中性",
            explain="收盘位于近252日高点75%以上，且5日均量>=20日均量1.5倍。",
        )
