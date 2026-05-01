"""
Context Providers — 不产生评分的"指标"，只负责向 context 注入共享中间量。

这些 Provider 解决了旧 calculate() 中指标间隐式共享中间变量的问题，
现在依赖关系通过 dependencies() / provide() 显式声明。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from .base import BaseIndicator, IndicatorMeta
from ..config import TRADING_DAYS_PER_YEAR
from ..models import IndicatorResult, MarketDataBundle, OptionChainSnapshot


# ────────────────────────────────────────────────────────────────────
# 1. OptionFrameProvider
# ────────────────────────────────────────────────────────────────────


class OptionFrameProvider(BaseIndicator):
    """将 bundle.option_chains 拍平为单一 DataFrame，写入 context["option_frame"]。"""

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="_option_frame_provider",
            category="internal",
            max_score=0,
            participates_in_voting=False,
        )

    def provide(self) -> List[str]:
        return ["option_frame"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        option_frame = self._flatten_option_chains(bundle.option_chains)
        context["option_frame"] = option_frame
        return IndicatorResult(
            name="_option_frame_provider",
            raw_value=None,
            score=0,
            available=False,
        )

    @staticmethod
    def _flatten_option_chains(chains: List[OptionChainSnapshot]) -> pd.DataFrame:
        frames: List[pd.DataFrame] = []
        for chain in chains:
            if chain.calls is not None and not chain.calls.empty:
                frames.append(chain.calls.copy())
            if chain.puts is not None and not chain.puts.empty:
                frames.append(chain.puts.copy())

        if not frames:
            return pd.DataFrame()

        data = pd.concat(frames, ignore_index=True)
        numeric_columns = [
            "strike",
            "volume",
            "openInterest",
            "impliedVolatility",
            "dte",
        ]
        for column in numeric_columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        data = data.dropna(subset=["strike", "dte"]).fillna(0.0)
        return data


# ────────────────────────────────────────────────────────────────────
# 2. SpotBaseProvider
# ────────────────────────────────────────────────────────────────────


class SpotBaseProvider(BaseIndicator):
    """预计算现货基础量：close, volume, daily_return, high_252 等。"""

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="_spot_base_provider",
            category="internal",
            max_score=0,
            participates_in_voting=False,
        )

    def provide(self) -> List[str]:
        return ["spot_close", "spot_volume", "daily_return", "high_252"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        history = bundle.spot_history.copy()
        close = history["Close"].dropna()
        volume = history["Volume"].fillna(0.0)

        if len(close) >= 2:
            latest_close = float(close.iloc[-1])
            prev_close = float(close.iloc[-2])
            daily_return = (
                latest_close / prev_close - 1 if prev_close > 0 else np.nan
            )
        else:
            daily_return = np.nan

        high_252 = float(close.tail(252).max()) if len(close) > 0 else np.nan

        context["spot_close"] = close
        context["spot_volume"] = volume
        context["daily_return"] = daily_return
        context["high_252"] = high_252

        return IndicatorResult(
            name="_spot_base_provider",
            raw_value=None,
            score=0,
            available=False,
        )


# ────────────────────────────────────────────────────────────────────
# 3. AtmIvProvider
# ────────────────────────────────────────────────────────────────────


class AtmIvProvider(BaseIndicator):
    """计算 ATM IV、HV20 等多个期权指标的公共中间量。"""

    def __init__(self, risk_free_rate: float = 0.04) -> None:
        self.risk_free_rate = risk_free_rate

    def meta(self) -> IndicatorMeta:
        return IndicatorMeta(
            name="_atm_iv_provider",
            category="internal",
            max_score=0,
            participates_in_voting=False,
        )

    def dependencies(self) -> List[str]:
        return ["option_frame"]

    def provide(self) -> List[str]:
        return ["call_iv", "put_iv", "atm_iv", "hv20"]

    def compute(
        self, bundle: MarketDataBundle, context: Dict[str, Any]
    ) -> IndicatorResult:
        option_frame: pd.DataFrame = context.get("option_frame", pd.DataFrame())

        # HV20
        close_prices = bundle.spot_history["Close"].dropna()
        returns = close_prices.pct_change().dropna()
        hv20 = (
            float(returns.tail(20).std() * math.sqrt(TRADING_DAYS_PER_YEAR))
            if len(returns) >= 20
            else np.nan
        )

        # ATM IV
        if option_frame.empty:
            call_iv, put_iv = np.nan, np.nan
        else:
            call_iv, put_iv = self._front_atm_call_put_iv(
                option_frame, bundle.spot_price
            )

        atm_iv = (
            float(np.nanmean([call_iv, put_iv]))
            if np.isfinite(call_iv) or np.isfinite(put_iv)
            else np.nan
        )

        context["call_iv"] = call_iv
        context["put_iv"] = put_iv
        context["atm_iv"] = atm_iv
        context["hv20"] = hv20

        return IndicatorResult(
            name="_atm_iv_provider",
            raw_value=None,
            score=0,
            available=False,
        )

    @staticmethod
    def _front_atm_call_put_iv(
        option_frame: pd.DataFrame, spot_price: float
    ) -> Tuple[float, float]:
        valid_dte = option_frame.loc[option_frame["dte"] >= 0, "dte"]
        if valid_dte.empty:
            return np.nan, np.nan

        front_dte = int(valid_dte.min())
        front = option_frame.loc[option_frame["dte"] == front_dte]

        call_frame = front.loc[front["optionType"] == "call"].copy()
        put_frame = front.loc[front["optionType"] == "put"].copy()

        if call_frame.empty or put_frame.empty:
            return np.nan, np.nan

        call_frame["moneyness"] = (call_frame["strike"] - spot_price).abs()
        put_frame["moneyness"] = (put_frame["strike"] - spot_price).abs()

        call_iv = float(
            call_frame.sort_values("moneyness").iloc[0]["impliedVolatility"]
        )
        put_iv = float(
            put_frame.sort_values("moneyness").iloc[0]["impliedVolatility"]
        )

        return call_iv, put_iv
