"""Zero Gamma — Gamma曲线翻转点。"""

from __future__ import annotations

from typing import Any, Dict, List

from ..base import BaseIndicator, IndicatorMeta
from ...config import UNAVAILABLE_INDICATORS
from ...models import IndicatorResult, MarketDataBundle


class ZeroGammaIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="Zero Gamma",
            category="gamma",
            max_score=0,
            participates_in_voting=False,
            description="Gamma曲线翻转点。",
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
                name="Zero Gamma",
                raw_value=None,
                score=0,
                signal="不可用",
                explain=f"{UNAVAILABLE_INDICATORS['Zero Gamma']} 原因: {reason}",
                available=False,
            )

        return IndicatorResult(
            name="Zero Gamma",
            raw_value=round(metrics.zero_gamma, 4) if metrics.zero_gamma is not None else None,
            score=0,
            signal="翻转线" if metrics.zero_gamma is not None else "不可用",
            explain=(
                metrics.explain
                if metrics.zero_gamma is not None
                else UNAVAILABLE_INDICATORS["Zero Gamma"]
            ),
            available=metrics.zero_gamma is not None,
        )
