from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class IndicatorResult:
    name: str
    raw_value: Any
    score: int
    signal: str = "中性"
    explain: str = ""
    available: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptionChainSnapshot:
    expiry: str
    dte: int
    calls: pd.DataFrame
    puts: pd.DataFrame


@dataclass
class GammaMetrics:
    net_gex: Optional[float]
    gamma_wall: Optional[float]
    zero_gamma: Optional[float]
    gex_regime: str
    contract_count: int
    explain: str


@dataclass
class MarketDataBundle:
    ticker: str
    as_of: date
    spot_history: pd.DataFrame
    benchmark_history: pd.DataFrame
    option_chains: List[OptionChainSnapshot]
    spot_price: float
    gamma_metrics: Optional[GammaMetrics] = None
    gamma_unavailable_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class RatingResult:
    ticker: str
    as_of: str
    option_indicators: Dict[str, IndicatorResult]
    spot_indicators: Dict[str, IndicatorResult]
    gamma_indicators: Dict[str, IndicatorResult]
    option_score: int
    spot_score: int
    resonance_bonus: int
    total_score: int
    option_direction: str
    spot_direction: str
    overall_direction: str
    resonance_label: str
    warnings: List[str] = field(default_factory=list)
    unavailable_indicators: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "as_of": self.as_of,
            "option_indicators": {
                key: value.to_dict() for key, value in self.option_indicators.items()
            },
            "spot_indicators": {
                key: value.to_dict() for key, value in self.spot_indicators.items()
            },
            "gamma_indicators": {
                key: value.to_dict() for key, value in self.gamma_indicators.items()
            },
            "option_score": self.option_score,
            "spot_score": self.spot_score,
            "resonance_bonus": self.resonance_bonus,
            "total_score": self.total_score,
            "option_direction": self.option_direction,
            "spot_direction": self.spot_direction,
            "overall_direction": self.overall_direction,
            "resonance_label": self.resonance_label,
            "warnings": self.warnings,
            "unavailable_indicators": self.unavailable_indicators,
        }
