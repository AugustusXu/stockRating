"""多行权价联动 — 统计 Vol/OI >= 3 的行权价个数。"""

from __future__ import annotations

from typing import Any, Dict, List

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class MultiStrikeIndicator(BaseIndicator):

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="多行权价联动",
            category="option",
            max_score=2,
            participates_in_voting=False,
            description="统计Vol/OI>=3的行权价个数。",
        )

    def dependencies(self) -> List[str]:
        return ["linked_strike_count"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        strike_count = context.get("linked_strike_count", 0)
        score = 2 if strike_count >= 3 else 0

        return IndicatorResult(
            name="多行权价联动",
            raw_value=int(strike_count),
            score=score,
            signal="异动" if score > 0 else "中性",
            explain="统计Vol/OI>=3的行权价个数。",
        )
