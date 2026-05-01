from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from .bull_screening import BullScreener
from .config import UNAVAILABLE_INDICATORS
from .data_loader import MarketDataLoader
from .indicators import IndicatorEngine, default_engine
from .models import GammaMetrics, IndicatorResult, MarketDataBundle, RatingResult
from .scoring import (
    classify_votes,
    compute_resonance,
    merge_overall_direction,
    sum_scores,
)


class StockRatingService:
    def __init__(
        self,
        source_preference: str = "yfinance_first",
        max_option_expiries: int = 3,
        use_cache: bool = True,
        engine: IndicatorEngine | None = None,
        bull_screener: BullScreener | None = None,
    ) -> None:
        self.loader = MarketDataLoader(
            source_preference=source_preference,
            max_option_expiries=max_option_expiries,
            use_cache=use_cache,
        )
        self.engine = engine or default_engine()
        self.bull_screener = bull_screener or BullScreener()

    def get_stock_rating(
        self,
        ticker: str,
        as_of: Optional[date] = None,
        gamma_inputs: Optional[Dict[str, Any]] = None,
        include_unavailable: bool = True,
    ) -> dict:
        bundle = self.loader.load(ticker=ticker, as_of=as_of)

        gamma_metrics, gamma_reason = self._build_gamma_metrics_from_inputs(gamma_inputs)
        bundle.gamma_metrics = gamma_metrics
        bundle.gamma_unavailable_reason = gamma_reason
        if gamma_metrics is None and gamma_reason:
            bundle.warnings.append(f"Gamma数据不可用: {gamma_reason}")

        # ── 通过引擎统一执行所有指标 ──
        all_indicators, (bull_votes, bear_votes) = self.engine.run(bundle)

        # ── 按 category 分组 ──
        option_indicators: Dict[str, IndicatorResult] = {}
        spot_indicators: Dict[str, IndicatorResult] = {}
        gamma_indicators: Dict[str, IndicatorResult] = {}

        for name, result in all_indicators.items():
            category = self.engine.get_category(name)
            if category == "option":
                option_indicators[name] = result
            elif category == "spot":
                spot_indicators[name] = result
            elif category == "gamma":
                gamma_indicators[name] = result

        # ── 评分 ──
        option_score = sum_scores(option_indicators)
        spot_score = sum_scores(spot_indicators)

        # ── 方向投票 ──
        # 引擎已经统一做了投票统计，但为了保持与旧逻辑一致
        # （期权和现货分开投票），这里按分组重新统计
        option_bull, option_bear = self._count_votes_for_category(option_indicators)
        spot_bull, spot_bear = self._count_votes_for_category(spot_indicators)

        # 现货补丁：如果所有指标都没投票，用 daily_return 做兜底
        if spot_bull == 0 and spot_bear == 0:
            close = bundle.spot_history["Close"].dropna()
            if len(close) >= 2:
                import numpy as np
                prev = float(close.iloc[-2])
                dr = float(close.iloc[-1]) / prev - 1 if prev > 0 else 0
                if dr > 0:
                    spot_bull = 1
                elif dr < 0:
                    spot_bear = 1

        option_direction = classify_votes(option_bull, option_bear)
        spot_direction = classify_votes(spot_bull, spot_bear)

        resonance_bonus, resonance_label, resonance_explain = compute_resonance(
            option_score=option_score,
            spot_score=spot_score,
            option_direction=option_direction,
            spot_direction=spot_direction,
        )

        total_score = option_score + spot_score + resonance_bonus
        overall_direction = merge_overall_direction(option_direction, spot_direction)

        warnings = list(bundle.warnings)
        warnings.append(f"共振判定: {resonance_explain}")

        result = RatingResult(
            ticker=bundle.ticker,
            as_of=bundle.as_of.isoformat(),
            option_indicators=option_indicators,
            spot_indicators=spot_indicators,
            gamma_indicators=gamma_indicators,
            option_score=option_score,
            spot_score=spot_score,
            resonance_bonus=resonance_bonus,
            total_score=total_score,
            option_direction=option_direction,
            spot_direction=spot_direction,
            overall_direction=overall_direction,
            resonance_label=resonance_label,
            warnings=warnings,
            unavailable_indicators=self._collect_unavailable_indicators(
                gamma_indicators=gamma_indicators,
                include_unavailable=include_unavailable,
            ),
        )
        result_dict = result.to_dict()

        # ── 正股看涨筛选 ──
        bull_result = self.bull_screener.screen(result_dict, bundle)
        result_dict["bull_screening"] = bull_result.to_dict()

        return result_dict

    def get_bulk_stock_ratings(
        self,
        tickers: Iterable[str],
        as_of: Optional[date] = None,
        gamma_inputs_by_ticker: Optional[Dict[str, Dict[str, Any]]] = None,
        include_unavailable: bool = True,
    ) -> List[dict]:
        results: List[dict] = []
        failures: List[dict] = []

        for ticker in tickers:
            try:
                ticker_key = str(ticker).upper()
                gamma_inputs = None
                if gamma_inputs_by_ticker:
                    gamma_inputs = gamma_inputs_by_ticker.get(ticker_key)

                result = self.get_stock_rating(
                    ticker=ticker,
                    as_of=as_of,
                    gamma_inputs=gamma_inputs,
                    include_unavailable=include_unavailable,
                )
                results.append(result)
            except Exception as exc:
                failures.append(
                    {
                        "ticker": str(ticker).upper(),
                        "error": str(exc),
                    }
                )

        results.sort(key=lambda item: item.get("total_score", -1), reverse=True)
        return results + failures

    def _count_votes_for_category(
        self, indicators: Dict[str, IndicatorResult]
    ) -> tuple[int, int]:
        """按分组统计投票（只统计 participates_in_voting 的指标）。"""
        bull, bear = 0, 0
        for name, result in indicators.items():
            if not result.available:
                continue
            # 检查该指标是否参与投票
            for ind in self.engine._indicators:
                m = ind.meta()
                if m.name == name and m.participates_in_voting:
                    if "看涨" in result.signal and "看跌" not in result.signal:
                        bull += 1
                    elif "看跌" in result.signal and "看涨" not in result.signal:
                        bear += 1
                    break
        return bull, bear

    def _build_gamma_metrics_from_inputs(
        self,
        gamma_inputs: Optional[Dict[str, Any]],
    ) -> tuple[Optional[GammaMetrics], Optional[str]]:
        if not gamma_inputs:
            return None, "未提供Gamma输入，请通过gamma_inputs传入GEX净值/GEX环境/γ Wall/Zero Gamma。"

        net_gex = self._to_float(
            gamma_inputs.get("gex_net", gamma_inputs.get("GEX净值"))
        )
        gamma_wall = self._to_float(
            gamma_inputs.get("gamma_wall", gamma_inputs.get("γ Wall"))
        )
        zero_gamma = self._to_float(
            gamma_inputs.get("zero_gamma", gamma_inputs.get("Zero Gamma"))
        )

        regime_value = gamma_inputs.get("gex_regime", gamma_inputs.get("GEX环境"))
        regime = str(regime_value).strip() if regime_value is not None else ""
        if not regime:
            if net_gex is not None:
                regime = "正Gamma" if net_gex >= 0 else "负Gamma"
            else:
                regime = "不可用"

        if (
            net_gex is None
            and gamma_wall is None
            and zero_gamma is None
            and regime == "不可用"
        ):
            return (
                None,
                "gamma_inputs已提供，但未解析到可用字段。可用键: gex_net/gex_regime/gamma_wall/zero_gamma。",
            )

        source = str(gamma_inputs.get("source", "财经网站输入")).strip() or "财经网站输入"
        metrics = GammaMetrics(
            net_gex=net_gex,
            gamma_wall=gamma_wall,
            zero_gamma=zero_gamma,
            gex_regime=regime,
            contract_count=0,
            explain=f"来自外部输入: {source}",
        )
        return metrics, None

    def _to_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _collect_unavailable_indicators(
        self,
        gamma_indicators: Dict[str, IndicatorResult],
        include_unavailable: bool,
    ) -> Dict[str, str]:
        if not include_unavailable:
            return {}

        unavailable: Dict[str, str] = {}
        for name, indicator in gamma_indicators.items():
            if not indicator.available:
                unavailable[name] = indicator.explain or UNAVAILABLE_INDICATORS.get(
                    name, "数据不可用"
                )

        return unavailable


def get_stock_rating(
    ticker: str,
    as_of: Optional[date] = None,
    gamma_inputs: Optional[Dict[str, Any]] = None,
    include_unavailable: bool = True,
    source_preference: str = "yfinance_first",
) -> dict:
    service = StockRatingService(
        source_preference=source_preference,
    )
    return service.get_stock_rating(
        ticker=ticker,
        as_of=as_of,
        gamma_inputs=gamma_inputs,
        include_unavailable=include_unavailable,
    )


def get_bulk_stock_ratings(
    tickers: Iterable[str],
    as_of: Optional[date] = None,
    gamma_inputs_by_ticker: Optional[Dict[str, Dict[str, Any]]] = None,
    include_unavailable: bool = True,
    source_preference: str = "yfinance_first",
) -> List[dict]:
    service = StockRatingService(
        source_preference=source_preference,
    )
    return service.get_bulk_stock_ratings(
        tickers=tickers,
        as_of=as_of,
        gamma_inputs_by_ticker=gamma_inputs_by_ticker,
        include_unavailable=include_unavailable,
    )
