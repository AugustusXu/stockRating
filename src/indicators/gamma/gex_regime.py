"""GEX环境 — 正/负Gamma环境判定。"""

from __future__ import annotations

from typing import Any, Dict, List

from ..base import BaseIndicator, IndicatorMeta
from ...config import UNAVAILABLE_INDICATORS
from ...models import IndicatorResult, MarketDataBundle


class GexRegimeIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="GEX环境",
            category="gamma",
            max_score=0,
            participates_in_voting=False,
            description="正/负Gamma环境判定。",
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
                name="GEX环境",
                raw_value=None,
                score=0,
                signal="不可用",
                explain=f"{UNAVAILABLE_INDICATORS['GEX环境']} 原因: {reason}",
                available=False,
            )

        return IndicatorResult(
            name="GEX环境",
            raw_value=metrics.gex_regime,
            score=0,
            signal=metrics.gex_regime,
            explain=metrics.explain,
            available=metrics.gex_regime != "不可用",
        )
