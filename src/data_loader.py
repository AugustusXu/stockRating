from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf

from .config import (
    BENCHMARK_TICKER,
    HISTORY_LOOKBACK_PERIOD,
    MAX_OPTION_EXPIRIES,
)
from .models import MarketDataBundle, OptionChainSnapshot


class MarketDataLoader:
    def __init__(
        self,
        source_preference: str = "yfinance_first",
        max_option_expiries: int = MAX_OPTION_EXPIRIES,
        use_cache: bool = True,
    ) -> None:
        self.source_preference = source_preference
        self.max_option_expiries = max_option_expiries
        self.use_cache = use_cache
        self._cache: Dict[Tuple[str, str], MarketDataBundle] = {}

    def load(self, ticker: str, as_of: Optional[date] = None) -> MarketDataBundle:
        symbol = ticker.upper().strip()
        cache_key = (symbol, as_of.isoformat() if as_of else "latest")

        if self.use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        warnings: List[str] = []

        spot_history = self._fetch_spot_history_yfinance(symbol)
        if spot_history.empty and self.source_preference != "yfinance_only":
            spot_history = self._fetch_spot_history_akshare(symbol, warnings)

        if spot_history.empty:
            raise ValueError(f"无法获取 {symbol} 的现货行情数据。")

        spot_history = self._normalize_spot_history(spot_history)
        if spot_history.empty:
            raise ValueError(f"{symbol} 的现货数据标准化后为空。")

        as_of_date = as_of or spot_history.index[-1].date()
        spot_history = spot_history.loc[spot_history.index.date <= as_of_date]
        if spot_history.empty:
            raise ValueError(f"{symbol} 在 {as_of_date} 之前没有可用行情。")

        if len(spot_history) < 60:
            warnings.append("现货历史数据不足60个交易日，部分指标可能不稳定。")

        benchmark_history = self._fetch_spot_history_yfinance(BENCHMARK_TICKER)
        if benchmark_history.empty and self.source_preference != "yfinance_only":
            benchmark_history = self._fetch_spot_history_akshare(BENCHMARK_TICKER, warnings)

        if benchmark_history.empty:
            raise ValueError("无法获取SPY基准数据，RS指标不可计算。")

        benchmark_history = self._normalize_spot_history(benchmark_history)
        benchmark_history = benchmark_history.loc[
            benchmark_history.index.date <= as_of_date
        ]

        if benchmark_history.empty:
            raise ValueError(f"SPY 在 {as_of_date} 之前没有可用行情。")

        option_chains = self._fetch_option_chains(symbol, as_of_date, warnings)

        bundle = MarketDataBundle(
            ticker=symbol,
            as_of=as_of_date,
            spot_history=spot_history,
            benchmark_history=benchmark_history,
            option_chains=option_chains,
            spot_price=float(spot_history["Close"].iloc[-1]),
            warnings=warnings,
        )

        if self.use_cache:
            self._cache[cache_key] = bundle

        return bundle

    def _fetch_spot_history_yfinance(self, symbol: str) -> pd.DataFrame:
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(
                period=HISTORY_LOOKBACK_PERIOD,
                interval="1d",
                auto_adjust=False,
                actions=False,
            )
            return data
        except Exception:
            return pd.DataFrame()

    def _fetch_spot_history_akshare(
        self, symbol: str, warnings: List[str]
    ) -> pd.DataFrame:
        try:
            import akshare as ak

            data = ak.stock_us_daily(symbol=symbol)
            if data is None or data.empty:
                return pd.DataFrame()
            return data
        except Exception as exc:
            warnings.append(f"akshare现货兜底失败: {exc}")
            return pd.DataFrame()

    def _normalize_spot_history(self, frame: pd.DataFrame) -> pd.DataFrame:
        data = frame.copy()

        if "Date" in data.columns:
            data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
            data = data.set_index("Date")

        rename_map = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "开盘": "Open",
            "最高": "High",
            "最低": "Low",
            "收盘": "Close",
            "成交量": "Volume",
            "日期": "Date",
        }
        data = data.rename(columns=rename_map)

        if "Date" in data.columns:
            data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
            data = data.set_index("Date")

        if not isinstance(data.index, pd.DatetimeIndex):
            data.index = pd.to_datetime(data.index, errors="coerce")

        if data.index.tz is not None:
            data.index = data.index.tz_localize(None)

        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        for column in required_columns:
            if column not in data.columns:
                data[column] = pd.NA
            data[column] = pd.to_numeric(data[column], errors="coerce")

        data = data[required_columns].sort_index()
        data = data.dropna(subset=["Close"]) 
        return data

    def _fetch_option_chains(
        self, symbol: str, as_of: date, warnings: List[str]
    ) -> List[OptionChainSnapshot]:
        option_snapshots: List[OptionChainSnapshot] = []

        try:
            ticker = yf.Ticker(symbol)
            expiries = list(ticker.options or [])
        except Exception as exc:
            warnings.append(f"期权到期日获取失败: {exc}")
            return option_snapshots

        if not expiries:
            warnings.append("当前标的没有可用期权链，期权维度将不可计算。")
            return option_snapshots

        selected_expiries = expiries[: self.max_option_expiries]

        for expiry in selected_expiries:
            try:
                chain = ticker.option_chain(expiry)
            except Exception as exc:
                warnings.append(f"期权链获取失败({expiry}): {exc}")
                continue

            dte = (pd.Timestamp(expiry).date() - as_of).days
            if dte < 0:
                continue

            calls = self._normalize_option_frame(chain.calls, expiry, dte, "call")
            puts = self._normalize_option_frame(chain.puts, expiry, dte, "put")

            option_snapshots.append(
                OptionChainSnapshot(expiry=expiry, dte=dte, calls=calls, puts=puts)
            )

        if not option_snapshots:
            warnings.append("期权链可用数据为空，期权分将回落为0。")

        return option_snapshots

    def _normalize_option_frame(
        self, frame: pd.DataFrame, expiry: str, dte: int, option_type: str
    ) -> pd.DataFrame:
        expected_columns = [
            "strike",
            "volume",
            "openInterest",
            "impliedVolatility",
            "lastPrice",
        ]

        if frame is None or frame.empty:
            return pd.DataFrame(columns=expected_columns + ["expiry", "dte", "optionType"])

        data = frame.copy()

        for column in expected_columns:
            if column not in data.columns:
                data[column] = 0.0
            data[column] = pd.to_numeric(data[column], errors="coerce")

        data["expiry"] = expiry
        data["dte"] = dte
        data["optionType"] = option_type

        data = data[expected_columns + ["expiry", "dte", "optionType"]]
        data = data.fillna(0.0)
        return data

