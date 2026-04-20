from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from .config import UNAVAILABLE_INDICATORS
from .data_loader import MarketDataLoader
from .features import OptionFeatureCalculator, SpotFeatureCalculator
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
    ) -> None:
        self.loader = MarketDataLoader(
            source_preference=source_preference,
            max_option_expiries=max_option_expiries,
            use_cache=use_cache,
        )
        self.option_calculator = OptionFeatureCalculator()
        self.spot_calculator = SpotFeatureCalculator()

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

        option_indicators, option_votes = self.option_calculator.calculate(bundle)
        spot_indicators, spot_votes = self.spot_calculator.calculate(bundle)
        gamma_indicators = self._build_gamma_indicators(bundle)

        option_score = sum_scores(option_indicators)
        spot_score = sum_scores(spot_indicators)

        option_direction = classify_votes(*option_votes)
        spot_direction = classify_votes(*spot_votes)

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
        return result.to_dict()

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

    def _build_gamma_indicators(
        self,
        bundle: MarketDataBundle,
    ) -> Dict[str, IndicatorResult]:
        metrics = bundle.gamma_metrics
        if metrics is None:
            runtime_reason = (
                bundle.gamma_unavailable_reason
                or "未提供Gamma指标输入，已切换为说明模式。"
            )
            return {
                "GEX净值": IndicatorResult(
                    name="GEX净值",
                    raw_value=None,
                    score=0,
                    signal="不可用",
                    explain=f"{UNAVAILABLE_INDICATORS['GEX净值']} 原因: {runtime_reason}",
                    available=False,
                ),
                "GEX环境": IndicatorResult(
                    name="GEX环境",
                    raw_value=None,
                    score=0,
                    signal="不可用",
                    explain=f"{UNAVAILABLE_INDICATORS['GEX环境']} 原因: {runtime_reason}",
                    available=False,
                ),
                "γ Wall": IndicatorResult(
                    name="γ Wall",
                    raw_value=None,
                    score=0,
                    signal="不可用",
                    explain=f"{UNAVAILABLE_INDICATORS['γ Wall']} 原因: {runtime_reason}",
                    available=False,
                ),
                "Zero Gamma": IndicatorResult(
                    name="Zero Gamma",
                    raw_value=None,
                    score=0,
                    signal="不可用",
                    explain=f"{UNAVAILABLE_INDICATORS['Zero Gamma']} 原因: {runtime_reason}",
                    available=False,
                ),
            }

        common_explain = metrics.explain
        gex_signal = "正Gamma" if (metrics.net_gex or 0.0) >= 0 else "负Gamma"

        indicators: Dict[str, IndicatorResult] = {
            "GEX净值": IndicatorResult(
                name="GEX净值",
                raw_value=round(metrics.net_gex, 4) if metrics.net_gex is not None else None,
                score=0,
                signal=gex_signal,
                explain=common_explain,
                available=metrics.net_gex is not None,
            ),
            "GEX环境": IndicatorResult(
                name="GEX环境",
                raw_value=metrics.gex_regime,
                score=0,
                signal=metrics.gex_regime,
                explain=common_explain,
                available=metrics.gex_regime != "不可用",
            ),
            "γ Wall": IndicatorResult(
                name="γ Wall",
                raw_value=round(metrics.gamma_wall, 4)
                if metrics.gamma_wall is not None
                else None,
                score=0,
                signal="关键位" if metrics.gamma_wall is not None else "不可用",
                explain=common_explain if metrics.gamma_wall is not None else UNAVAILABLE_INDICATORS["γ Wall"],
                available=metrics.gamma_wall is not None,
            ),
            "Zero Gamma": IndicatorResult(
                name="Zero Gamma",
                raw_value=round(metrics.zero_gamma, 4)
                if metrics.zero_gamma is not None
                else None,
                score=0,
                signal="翻转线" if metrics.zero_gamma is not None else "不可用",
                explain=(
                    common_explain
                    if metrics.zero_gamma is not None
                    else UNAVAILABLE_INDICATORS["Zero Gamma"]
                ),
                available=metrics.zero_gamma is not None,
            ),
        }

        return indicators

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
