"""GEX净值 — 净Gamma Exposure方向判定。"""

from __future__ import annotations

from typing import Any, Dict, List

from ..base import BaseIndicator, IndicatorMeta
from ...config import UNAVAILABLE_INDICATORS
from ...models import IndicatorResult, MarketDataBundle


class GexNetIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="GEX净值",
            category="gamma",
            max_score=0,
            participates_in_voting=False,
            description="净Gamma Exposure方向判定。",
        )

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        metrics = bundle.gamma_metrics
        if metrics is None:
            reason = (
                bundle.gamma_unavailable_reason
                or "未提供Gamma指标输入，已切换为说明模式。"
            )
            return IndicatorResult(
                name="GEX净值",
                raw_value=None,
                score=0,
                signal="不可用",
                explain=f"{UNAVAILABLE_INDICATORS['GEX净值']} 原因: {reason}",
                available=False,
            )

        gex_signal = "正Gamma" if (metrics.net_gex or 0.0) >= 0 else "负Gamma"

        return IndicatorResult(
            name="GEX净值",
            raw_value=round(metrics.net_gex, 4) if metrics.net_gex is not None else None,
            score=0,
            signal=gex_signal,
            explain=metrics.explain,
            available=metrics.net_gex is not None,
        )
