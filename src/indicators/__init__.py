"""
指标插件系统 — 每个指标是一个独立的类，通过 IndicatorEngine 统一注册和调度。
"""

from .base import BaseIndicator, IndicatorMeta
from .engine import IndicatorEngine

from .context_providers import AtmIvProvider, OptionFrameProvider, SpotBaseProvider
from .option.vol_oi import VolOiIndicator
from .option.pc_ratio import PcRatioIndicator
from .option.iv_skew import IvSkewIndicator
from .option.multi_strike import MultiStrikeIndicator
from .option.delta_direction import DeltaDirectionIndicator
from .option.iv_hv import IvHvIndicator
from .option.short_dte import ShortDteIndicator
from .spot.high_volume import HighVolumeIndicator
from .spot.strong_candle import StrongCandleIndicator
from .spot.relative_strength import RelativeStrengthIndicator
from .spot.consecutive_volume import ConsecutiveVolumeIndicator
from .spot.bollinger_squeeze import BollingerSqueezeIndicator
from .spot.vol_expansion import VolExpansionIndicator
from .gamma.gex_net import GexNetIndicator
from .gamma.gex_regime import GexRegimeIndicator
from .gamma.gamma_wall import GammaWallIndicator
from .gamma.zero_gamma import ZeroGammaIndicator


def default_engine(risk_free_rate: float = 0.04) -> IndicatorEngine:
    """创建包含全部默认指标的引擎实例。"""
    engine = IndicatorEngine()
    engine.register_all(
        [
            # ── 数据预处理器（不产生评分，只准备 context）──
            OptionFrameProvider(),
            SpotBaseProvider(),
            AtmIvProvider(risk_free_rate=risk_free_rate),
            # ── 期权指标 ──
            VolOiIndicator(),
            PcRatioIndicator(),
            IvSkewIndicator(),
            MultiStrikeIndicator(),
            DeltaDirectionIndicator(risk_free_rate=risk_free_rate),
            IvHvIndicator(),
            ShortDteIndicator(),
            # ── 现货指标 ──
            HighVolumeIndicator(),
            StrongCandleIndicator(),
            RelativeStrengthIndicator(),
            ConsecutiveVolumeIndicator(),
            BollingerSqueezeIndicator(),
            VolExpansionIndicator(),
            # ── Gamma 指标 ──
            GexNetIndicator(),
            GexRegimeIndicator(),
            GammaWallIndicator(),
            ZeroGammaIndicator(),
        ]
    )
    return engine


__all__ = [
    "BaseIndicator",
    "IndicatorMeta",
    "IndicatorEngine",
    "default_engine",
]
