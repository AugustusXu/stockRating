"""⑩ 机构布局期限 — DTE>30天=2分, DTE>14天=1分。"""

from __future__ import annotations

from typing import Any, Dict

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class InstitutionalDteDimension(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="机构布局期限(看涨)",
            category="bull",
            max_score=2,
            participates_in_voting=False,
            description="DTE越长=中长线战略建仓，资金更粘。",
        )

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        active_dte = context.get("active_dte")
        if active_dte is None:
            return IndicatorResult(
                name="机构布局期限(看涨)",
                raw_value=None,
                score=0,
                signal="不可用",
                explain="DTE数据缺失。",
                available=False,
            )

        if active_dte > 30:
            score, signal = 2, "战略建仓"
        elif active_dte > 14:
            score, signal = 1, "中线布局"
        else:
            score, signal = 0, "短线"

        return IndicatorResult(
            name="机构布局期限(看涨)",
            raw_value=int(active_dte),
            score=score,
            signal=signal,
            explain="聪明钱选的到期日暴露长线意图。",
        )
