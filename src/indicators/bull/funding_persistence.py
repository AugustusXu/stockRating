"""⑧ 资金持续性 — 连续放量>=3天=2分, 放量比>=2.0x=1分。"""

from __future__ import annotations

from typing import Any, Dict

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class FundingPersistenceDimension(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="资金持续性(看涨)",
            category="bull",
            max_score=2,
            participates_in_voting=False,
            description="连续放量=持续有新资金流入。",
        )

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        consecutive_burst = context.get("consecutive_volume_burst", False)
        vol_5d_20d = context.get("vol_5d_20d")

        if consecutive_burst:
            score, signal = 2, "连续放量"
            explain = "连续3天成交量均超过20日均量1.3倍。"
        elif vol_5d_20d is not None and vol_5d_20d >= 2.0:
            score, signal = 1, "放量"
            explain = f"5日/20日均量比={round(vol_5d_20d, 2)}x，≥2.0倍。"
        else:
            score, signal = 0, "无放量"
            explain = "未检测到显著放量信号。"

        return IndicatorResult(
            name="资金持续性(看涨)",
            raw_value={
                "consecutive_burst": consecutive_burst,
                "vol_5d_20d": round(vol_5d_20d, 4) if vol_5d_20d is not None else None,
            },
            score=score,
            signal=signal,
            explain=explain,
        )
