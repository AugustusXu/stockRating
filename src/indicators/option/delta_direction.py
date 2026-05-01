"""Delta加权方向 — Black-Scholes估算Delta后做volume加权汇总。"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..base import BaseIndicator, IndicatorMeta
from ...models import IndicatorResult, MarketDataBundle


class DeltaDirectionIndicator(BaseIndicator):

    def __init__(self, risk_free_rate: float = 0.04) -> None:
        self.risk_free_rate = risk_free_rate

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="Delta加权方向",
            category="option",
            max_score=3,
            participates_in_voting=True,
            description="Black-Scholes估算Delta后做volume加权汇总。",
        )

    def dependencies(self) -> List[str]:
        return ["option_frame", "atm_iv"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        option_frame: pd.DataFrame = context.get("option_frame", pd.DataFrame())
        atm_iv = context.get("atm_iv", np.nan)

        if option_frame.empty:
            return IndicatorResult(
                name="Delta加权方向",
                raw_value=None,
                score=0,
                signal="中性",
                explain="期权链数据为空，无法计算该指标。",
                available=False,
            )

        net_delta = self._net_delta_exposure(
            option_frame, bundle.spot_price, atm_iv
        )

        if not np.isfinite(net_delta):
            return IndicatorResult(
                name="Delta加权方向",
                raw_value=None,
                score=0,
                signal="中性",
                explain="缺少可用期权链，净Delta不可计算。",
                available=False,
            )

        score = 3 if abs(net_delta) >= 5000 else 0
        if net_delta >= 1000:
            signal = "看涨"
        elif net_delta <= -1000:
            signal = "看跌"
        else:
            signal = "中性"

        return IndicatorResult(
            name="Delta加权方向",
            raw_value=round(net_delta, 2),
            score=score,
            signal=signal,
            explain="Black-Scholes估算Delta后做volume加权汇总。",
        )

    def _net_delta_exposure(
        self, option_frame: pd.DataFrame, spot_price: float, fallback_iv: float
    ) -> float:
        if option_frame.empty:
            return np.nan

        deltas: List[float] = []
        for _, row in option_frame.iterrows():
            sigma = float(row["impliedVolatility"])
            if sigma <= 0 and np.isfinite(fallback_iv):
                sigma = float(fallback_iv)
            if sigma <= 0:
                sigma = 0.35

            strike = float(row["strike"])
            dte = max(float(row["dte"]), 1.0)
            option_type = str(row["optionType"])

            delta = self._estimate_delta(
                spot=spot_price,
                strike=strike,
                dte=dte,
                sigma=sigma,
                option_type=option_type,
            )
            notional_delta = delta * float(row["volume"]) * 100.0
            deltas.append(notional_delta)

        return float(np.sum(deltas)) if deltas else np.nan

    def _estimate_delta(
        self,
        spot: float,
        strike: float,
        dte: float,
        sigma: float,
        option_type: str,
    ) -> float:
        if spot <= 0 or strike <= 0 or sigma <= 0:
            return 0.0

        t = max(dte / 365.0, 1.0 / 365.0)
        sqrt_t = math.sqrt(t)

        d1 = (
            math.log(spot / strike)
            + (self.risk_free_rate + 0.5 * sigma * sigma) * t
        ) / (sigma * sqrt_t)

        cdf = NormalDist().cdf(d1)
        if option_type == "call":
            return float(cdf)
        return float(cdf - 1.0)
