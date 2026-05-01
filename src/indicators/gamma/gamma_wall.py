"""γ Wall — 做市商最大Gamma暴露的行权价。"""

from __future__ import annotations

from typing import Any, Dict, List

from ..base import BaseIndicator, IndicatorMeta
from ...config import UNAVAILABLE_INDICATORS
from ...models import IndicatorResult, MarketDataBundle


class GammaWallIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="γ Wall",
            category="gamma",
            max_score=0,
            participates_in_voting=False,
            description="做市商最大Gamma暴露的行权价。",
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
                name="γ Wall",
                raw_value=None,
                score=0,
                signal="不可用",
                explain=f"{UNAVAILABLE_INDICATORS['γ Wall']} 原因: {reason}",
                available=False,
            )

        return IndicatorResult(
            name="γ Wall",
            raw_value=round(metrics.gamma_wall, 4) if metrics.gamma_wall is not None else None,
            score=0,
            signal="关键位" if metrics.gamma_wall is not None else "不可用",
            explain=metrics.explain if metrics.gamma_wall is not None else UNAVAILABLE_INDICATORS["γ Wall"],
            available=metrics.gamma_wall is not None,
        )
