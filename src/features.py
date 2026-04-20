from __future__ import annotations

import math
from statistics import NormalDist
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .config import OPTION_INDICATOR_NAMES, SPOT_INDICATOR_NAMES, TRADING_DAYS_PER_YEAR
from .models import IndicatorResult, MarketDataBundle, OptionChainSnapshot


class OptionFeatureCalculator:
    def __init__(self, risk_free_rate: float = 0.04) -> None:
        self.risk_free_rate = risk_free_rate

    def calculate(
        self, bundle: MarketDataBundle
    ) -> Tuple[Dict[str, IndicatorResult], Tuple[int, int]]:
        option_frame = self._flatten_option_chains(bundle.option_chains)
        if option_frame.empty:
            indicators = {
                name: IndicatorResult(
                    name=name,
                    raw_value=None,
                    score=0,
                    signal="中性",
                    explain="期权链数据为空，无法计算该指标。",
                    available=False,
                )
                for name in OPTION_INDICATOR_NAMES
            }
            return indicators, (0, 0)

        close_prices = bundle.spot_history["Close"].dropna()
        returns = close_prices.pct_change().dropna()
        hv20 = (
            float(returns.tail(20).std() * math.sqrt(TRADING_DAYS_PER_YEAR))
            if len(returns) >= 20
            else np.nan
        )

        total_call_volume = float(
            option_frame.loc[option_frame["optionType"] == "call", "volume"].sum()
        )
        total_put_volume = float(
            option_frame.loc[option_frame["optionType"] == "put", "volume"].sum()
        )
        pc_ratio = (
            total_put_volume / total_call_volume if total_call_volume > 0 else np.nan
        )

        valid_voi = option_frame[
            (option_frame["volume"] > 0) & (option_frame["openInterest"] > 0)
        ].copy()
        if valid_voi.empty:
            max_voi_ratio = np.nan
            linked_strike_count = 0
        else:
            valid_voi["vol_oi_ratio"] = valid_voi["volume"] / valid_voi["openInterest"]
            max_voi_ratio = float(valid_voi["vol_oi_ratio"].max())
            linked_strike_count = int(
                valid_voi.loc[valid_voi["vol_oi_ratio"] >= 3, "strike"].nunique()
            )

        call_iv, put_iv = self._front_atm_call_put_iv(option_frame, bundle.spot_price)
        iv_skew = (
            float(call_iv - put_iv)
            if np.isfinite(call_iv) and np.isfinite(put_iv)
            else np.nan
        )
        atm_iv = (
            float(np.nanmean([call_iv, put_iv]))
            if np.isfinite(call_iv) or np.isfinite(put_iv)
            else np.nan
        )
        iv_hv_ratio = (
            float(atm_iv / hv20)
            if np.isfinite(atm_iv) and np.isfinite(hv20) and hv20 > 0
            else np.nan
        )

        net_delta = self._net_delta_exposure(option_frame, bundle.spot_price, atm_iv)

        if float(option_frame["volume"].sum()) > 0:
            active_row = option_frame.sort_values("volume", ascending=False).iloc[0]
            active_dte = int(active_row["dte"])
        else:
            active_dte = int(option_frame["dte"].min())

        indicators: Dict[str, IndicatorResult] = {
            "Vol/OI极端": self._score_vol_oi(max_voi_ratio),
            "P/C Ratio": self._score_pc_ratio(pc_ratio),
            "IV Skew反转": self._score_iv_skew(iv_skew),
            "多行权价联动": self._score_multi_strike(linked_strike_count),
            "Delta加权方向": self._score_delta_direction(net_delta),
            "IV/HV比率": self._score_iv_hv(iv_hv_ratio, atm_iv, hv20),
            "末日期权效应": self._score_short_dte(active_dte),
        }

        bull_votes, bear_votes = self._count_votes(
            [
                indicators["P/C Ratio"].signal,
                indicators["IV Skew反转"].signal,
                indicators["Delta加权方向"].signal,
            ]
        )

        return indicators, (bull_votes, bear_votes)

    def _flatten_option_chains(
        self, chains: List[OptionChainSnapshot]
    ) -> pd.DataFrame:
        frames: List[pd.DataFrame] = []
        for chain in chains:
            if chain.calls is not None and not chain.calls.empty:
                frames.append(chain.calls.copy())
            if chain.puts is not None and not chain.puts.empty:
                frames.append(chain.puts.copy())

        if not frames:
            return pd.DataFrame()

        data = pd.concat(frames, ignore_index=True)
        numeric_columns = ["strike", "volume", "openInterest", "impliedVolatility", "dte"]
        for column in numeric_columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        data = data.dropna(subset=["strike", "dte"]).fillna(0.0)
        return data

    def _front_atm_call_put_iv(
        self, option_frame: pd.DataFrame, spot_price: float
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

        call_iv = float(call_frame.sort_values("moneyness").iloc[0]["impliedVolatility"])
        put_iv = float(put_frame.sort_values("moneyness").iloc[0]["impliedVolatility"])

        return call_iv, put_iv

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
            math.log(spot / strike) + (self.risk_free_rate + 0.5 * sigma * sigma) * t
        ) / (sigma * sqrt_t)

        cdf = NormalDist().cdf(d1)
        if option_type == "call":
            return float(cdf)
        return float(cdf - 1.0)

    def _score_vol_oi(self, ratio: float) -> IndicatorResult:
        if not np.isfinite(ratio):
            return IndicatorResult(
                name="Vol/OI极端",
                raw_value=None,
                score=0,
                signal="中性",
                explain="缺少有效volume/openInterest组合。",
                available=False,
            )

        if ratio >= 10:
            score = 5
        elif ratio >= 5:
            score = 3
        elif ratio >= 3:
            score = 1
        else:
            score = 0

        return IndicatorResult(
            name="Vol/OI极端",
            raw_value=round(ratio, 4),
            score=score,
            signal="异动" if score > 0 else "中性",
            explain="按最大成交量/持仓量比值分档打分。",
        )

    def _score_pc_ratio(self, pc_ratio: float) -> IndicatorResult:
        if not np.isfinite(pc_ratio):
            return IndicatorResult(
                name="P/C Ratio",
                raw_value=None,
                score=0,
                signal="中性",
                explain="缺少有效看涨成交量，P/C不可计算。",
                available=False,
            )

        if pc_ratio < 0.3:
            score, signal = 3, "强看涨"
        elif pc_ratio < 0.5:
            score, signal = 1, "偏看涨"
        elif pc_ratio > 3.0:
            score, signal = 3, "强看跌"
        elif pc_ratio > 2.0:
            score, signal = 1, "偏看跌"
        else:
            score, signal = 0, "中性"

        return IndicatorResult(
            name="P/C Ratio",
            raw_value=round(pc_ratio, 4),
            score=score,
            signal=signal,
            explain="按看跌成交量/看涨成交量分档。",
        )

    def _score_iv_skew(self, iv_skew: float) -> IndicatorResult:
        if not np.isfinite(iv_skew):
            return IndicatorResult(
                name="IV Skew反转",
                raw_value=None,
                score=0,
                signal="中性",
                explain="无法定位前月ATM的Call/Put IV。",
                available=False,
            )

        score = 3 if iv_skew > 0 else 0
        if iv_skew > 0.1:
            signal = "看涨"
        elif iv_skew < -0.1:
            signal = "看跌"
        else:
            signal = "中性"

        return IndicatorResult(
            name="IV Skew反转",
            raw_value=round(iv_skew, 4),
            score=score,
            signal=signal,
            explain="使用近月ATM: Call IV - Put IV。",
        )

    def _score_multi_strike(self, strike_count: int) -> IndicatorResult:
        score = 2 if strike_count >= 3 else 0
        return IndicatorResult(
            name="多行权价联动",
            raw_value=int(strike_count),
            score=score,
            signal="异动" if score > 0 else "中性",
            explain="统计Vol/OI>=3的行权价个数。",
        )

    def _score_delta_direction(self, net_delta: float) -> IndicatorResult:
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

    def _score_iv_hv(
        self, ratio: float, atm_iv: float, hv20: float
    ) -> IndicatorResult:
        if not np.isfinite(ratio):
            return IndicatorResult(
                name="IV/HV比率",
                raw_value={
                    "atm_iv": round(float(atm_iv), 4) if np.isfinite(atm_iv) else None,
                    "hv20": round(float(hv20), 4) if np.isfinite(hv20) else None,
                    "iv_hv": None,
                },
                score=0,
                signal="中性",
                explain="ATM IV或HV不足，IV/HV不可计算。",
                available=False,
            )

        if ratio > 2.0:
            score, signal = 3, "波动溢价高"
        elif ratio > 1.5:
            score, signal = 2, "波动偏贵"
        elif ratio < 0.5:
            score, signal = 3, "波动极低估"
        elif ratio < 0.7:
            score, signal = 2, "波动低估"
        else:
            score, signal = 0, "中性"

        return IndicatorResult(
            name="IV/HV比率",
            raw_value={
                "atm_iv": round(float(atm_iv), 4) if np.isfinite(atm_iv) else None,
                "hv20": round(float(hv20), 4) if np.isfinite(hv20) else None,
                "iv_hv": round(float(ratio), 4),
            },
            score=score,
            signal=signal,
            explain="ATM IV与20日历史波动率比值。",
        )

    def _score_short_dte(self, dte: int) -> IndicatorResult:
        score = 2 if dte <= 5 else 0
        return IndicatorResult(
            name="末日期权效应",
            raw_value=int(dte),
            score=score,
            signal="近到期" if score > 0 else "常规",
            explain="最活跃合约DTE<=5则加分。",
        )

    def _count_votes(self, signals: List[str]) -> Tuple[int, int]:
        bull_votes = 0
        bear_votes = 0

        for signal in signals:
            if "看涨" in signal and "看跌" not in signal:
                bull_votes += 1
            elif "看跌" in signal and "看涨" not in signal:
                bear_votes += 1

        return bull_votes, bear_votes


class SpotFeatureCalculator:
    def calculate(
        self, bundle: MarketDataBundle
    ) -> Tuple[Dict[str, IndicatorResult], Tuple[int, int]]:
        history = bundle.spot_history.copy()
        benchmark = bundle.benchmark_history.copy()

        close = history["Close"].dropna()
        volume = history["Volume"].fillna(0.0)

        if len(close) < 2:
            indicators = {
                name: IndicatorResult(
                    name=name,
                    raw_value=None,
                    score=0,
                    signal="中性",
                    explain="现货历史数据不足，无法计算。",
                    available=False,
                )
                for name in SPOT_INDICATOR_NAMES
            }
            return indicators, (0, 0)

        latest_close = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])
        daily_return = latest_close / prev_close - 1 if prev_close > 0 else np.nan

        high_252 = float(close.tail(252).max())
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

        high_volume_indicator = IndicatorResult(
            name="高位放量",
            raw_value={
                "close_to_252h": round(close_to_high, 4) if np.isfinite(close_to_high) else None,
                "vol_5d_20d": round(vol_ratio, 4) if np.isfinite(vol_ratio) else None,
            },
            score=3 if high_volume_at_high else 0,
            signal="看涨" if high_volume_at_high else "中性",
            explain="收盘位于近252日高点75%以上，且5日均量>=20日均量1.5倍。",
        )

        strong_candle_score = 1 if np.isfinite(daily_return) and daily_return > 0.05 else 0
        if np.isfinite(daily_return) and daily_return > 0.05:
            strong_candle_signal = "看涨"
        elif np.isfinite(daily_return) and daily_return < -0.05:
            strong_candle_signal = "看跌"
        else:
            strong_candle_signal = "中性"

        strong_candle_indicator = IndicatorResult(
            name="强阳柱",
            raw_value=round(float(daily_return), 4) if np.isfinite(daily_return) else None,
            score=strong_candle_score,
            signal=strong_candle_signal,
            explain="当日涨幅>5%记1分。",
        )

        rs_indicator = self._score_relative_strength(close, benchmark)
        consecutive_volume_indicator = self._score_consecutive_volume(volume, daily_return)
        bollinger_indicator = self._score_bollinger_squeeze(close)
        vol_expansion_indicator = self._score_vol_expansion(close, daily_return)

        indicators = {
            "高位放量": high_volume_indicator,
            "强阳柱": strong_candle_indicator,
            "RS vs SPY": rs_indicator,
            "连续放量>=3天": consecutive_volume_indicator,
            "布林带压缩": bollinger_indicator,
            "波动率扩张": vol_expansion_indicator,
        }

        bull_votes, bear_votes = self._count_votes(
            [item.signal for item in indicators.values() if item.available]
        )

        if bull_votes == 0 and bear_votes == 0 and np.isfinite(daily_return):
            if daily_return > 0:
                bull_votes = 1
            elif daily_return < 0:
                bear_votes = 1

        return indicators, (bull_votes, bear_votes)

    def _score_relative_strength(
        self, close: pd.Series, benchmark: pd.DataFrame
    ) -> IndicatorResult:
        benchmark_close = benchmark["Close"].dropna()
        if len(close) < 21 or len(benchmark_close) < 21:
            return IndicatorResult(
                name="RS vs SPY",
                raw_value=None,
                score=0,
                signal="中性",
                explain="股票或SPY历史不足21个交易日。",
                available=False,
            )

        stock_ret20 = float(close.iloc[-1] / close.iloc[-21] - 1)
        spy_ret20 = float(benchmark_close.iloc[-1] / benchmark_close.iloc[-21] - 1)
        rs = stock_ret20 - spy_ret20

        if rs > 0.10:
            score = 2
        elif rs > 0.05:
            score = 1
        else:
            score = 0

        if rs > 0:
            signal = "看涨"
        elif rs < 0:
            signal = "看跌"
        else:
            signal = "中性"

        return IndicatorResult(
            name="RS vs SPY",
            raw_value={
                "stock_ret20": round(stock_ret20, 4),
                "spy_ret20": round(spy_ret20, 4),
                "rs": round(rs, 4),
            },
            score=score,
            signal=signal,
            explain="20日超额收益=个股收益-SPY收益。",
        )

    def _score_consecutive_volume(
        self, volume: pd.Series, daily_return: float
    ) -> IndicatorResult:
        if len(volume) < 23:
            return IndicatorResult(
                name="连续放量>=3天",
                raw_value=None,
                score=0,
                signal="中性",
                explain="成交量历史不足23个交易日。",
                available=False,
            )

        rolling20 = volume.rolling(20).mean()
        condition = (volume > rolling20 * 1.3).fillna(False)
        three_day_burst = bool(condition.tail(3).all())

        if three_day_burst and np.isfinite(daily_return) and daily_return > 0:
            signal = "看涨"
        elif three_day_burst and np.isfinite(daily_return) and daily_return < 0:
            signal = "看跌"
        else:
            signal = "中性"

        return IndicatorResult(
            name="连续放量>=3天",
            raw_value=bool(three_day_burst),
            score=1 if three_day_burst else 0,
            signal=signal,
            explain="最近3天成交量均高于各自20日均量的1.3倍。",
        )

    def _score_bollinger_squeeze(self, close: pd.Series) -> IndicatorResult:
        if len(close) < 20:
            return IndicatorResult(
                name="布林带压缩",
                raw_value=None,
                score=0,
                signal="中性",
                explain="收盘价历史不足20个交易日。",
                available=False,
            )

        rolling_mean = close.rolling(20).mean().iloc[-1]
        rolling_std = close.rolling(20).std().iloc[-1]

        if not np.isfinite(rolling_mean) or rolling_mean <= 0 or not np.isfinite(rolling_std):
            return IndicatorResult(
                name="布林带压缩",
                raw_value=None,
                score=0,
                signal="中性",
                explain="布林带计算失败。",
                available=False,
            )

        width = float((4 * rolling_std) / rolling_mean)
        is_squeeze = width < 0.03

        return IndicatorResult(
            name="布林带压缩",
            raw_value=round(width, 4),
            score=1 if is_squeeze else 0,
            signal="蓄力" if is_squeeze else "中性",
            explain="布林带宽度=(Upper-Lower)/Middle，阈值取3%。",
        )

    def _score_vol_expansion(
        self, close: pd.Series, daily_return: float
    ) -> IndicatorResult:
        returns = close.pct_change().dropna()
        if len(returns) < 50:
            return IndicatorResult(
                name="波动率扩张",
                raw_value=None,
                score=0,
                signal="中性",
                explain="收益率历史不足50个交易日。",
                available=False,
            )

        hv10 = float(returns.tail(10).std() * math.sqrt(TRADING_DAYS_PER_YEAR))
        hv50 = float(returns.tail(50).std() * math.sqrt(TRADING_DAYS_PER_YEAR))
        expansion = hv10 > hv50

        if expansion and np.isfinite(daily_return) and daily_return > 0:
            signal = "看涨"
        elif expansion and np.isfinite(daily_return) and daily_return < 0:
            signal = "看跌"
        else:
            signal = "中性"

        return IndicatorResult(
            name="波动率扩张",
            raw_value={"hv10": round(hv10, 4), "hv50": round(hv50, 4)},
            score=1 if expansion else 0,
            signal=signal,
            explain="短期HV(10d)大于长期HV(50d)记1分。",
        )

    def _count_votes(self, signals: List[str]) -> Tuple[int, int]:
        bull_votes = 0
        bear_votes = 0

        for signal in signals:
            if "看涨" in signal and "看跌" not in signal:
                bull_votes += 1
            elif "看跌" in signal and "看涨" not in signal:
                bear_votes += 1

        return bull_votes, bear_votes
