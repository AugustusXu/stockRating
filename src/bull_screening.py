"""
BullScreener — 正股看涨筛选服务。

基于已有的评分结果，应用硬性筛选条件，然后从 10 个维度评分，
产出 BullScreeningResult。

对应 ratingDetails.md 第五章。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .indicators.base import BaseIndicator
from .indicators.engine import IndicatorEngine
from .indicators.bull import (
    DeltaStrengthDimension,
    FundingPersistenceDimension,
    GammaWallBreakoutDimension,
    InstitutionalDteDimension,
    IvHvBullDimension,
    IvSkewBullDimension,
    PcRatioBullDimension,
    ResonanceBullDimension,
    RsBullDimension,
    VolatilityStateDimension,
)
from .models import BullScreeningResult, MarketDataBundle


def default_bull_engine() -> IndicatorEngine:
    """创建看涨筛选的 10 维度引擎。"""
    engine = IndicatorEngine()
    engine.register_all(
        [
            GammaWallBreakoutDimension(),   # ① γ Wall 突破位置
            DeltaStrengthDimension(),       # ② Delta 方向强度
            PcRatioBullDimension(),         # ③ P/C Ratio
            IvSkewBullDimension(),          # ④ IV Skew 反转
            ResonanceBullDimension(),       # ⑤ 期现共振
            RsBullDimension(),              # ⑥ RS% 相对强度
            IvHvBullDimension(),            # ⑦ IV/HV 波动定价
            FundingPersistenceDimension(),  # ⑧ 资金持续性
            VolatilityStateDimension(),     # ⑨ 波动率状态
            InstitutionalDteDimension(),    # ⑩ 机构布局期限
        ]
    )
    return engine


class BullScreener:
    """
    正股看涨筛选器。

    使用方式:
        screener = BullScreener()
        result = screener.screen(rating_dict, bundle)
        if result.passed_filter:
            print(result.bull_score, result.tier)
    """

    def __init__(
        self,
        engine: IndicatorEngine | None = None,
        min_total_score: int = 8,
    ) -> None:
        self.engine = engine or default_bull_engine()
        self.min_total_score = min_total_score

    def screen(
        self,
        rating: dict,
        bundle: MarketDataBundle,
    ) -> BullScreeningResult:
        """
        对一个已完成基础评分的标的执行看涨筛选。

        Args:
            rating: get_stock_rating() 的返回结果字典。
            bundle: 原始市场数据包。

        Returns:
            BullScreeningResult
        """
        # ── 1. 提取关键值 ──
        spot_price = bundle.spot_price
        gamma_wall = self._extract_gamma_value(rating, "γ Wall")
        zero_gamma = self._extract_gamma_value(rating, "Zero Gamma")
        gex_regime = self._extract_gamma_signal(rating, "GEX环境")
        net_delta = self._extract_raw_value(
            rating, "option_indicators", "Delta加权方向"
        )
        pc_ratio = self._extract_raw_value(
            rating, "option_indicators", "P/C Ratio"
        )
        iv_skew = self._extract_raw_value(
            rating, "option_indicators", "IV Skew反转"
        )
        iv_hv_raw = self._extract_raw_value(
            rating, "option_indicators", "IV/HV比率"
        )
        iv_hv_ratio = (
            iv_hv_raw.get("iv_hv") if isinstance(iv_hv_raw, dict) else None
        )

        rs_raw = self._extract_raw_value(
            rating, "spot_indicators", "RS vs SPY"
        )
        rs = rs_raw.get("rs") if isinstance(rs_raw, dict) else None

        daily_return = self._extract_raw_value(
            rating, "spot_indicators", "强阳柱"
        )
        active_dte = self._extract_raw_value(
            rating, "option_indicators", "末日期权效应"
        )

        consecutive_burst = self._extract_raw_value(
            rating, "spot_indicators", "连续放量>=3天"
        )

        high_vol_raw = self._extract_raw_value(
            rating, "spot_indicators", "高位放量"
        )
        vol_5d_20d = (
            high_vol_raw.get("vol_5d_20d")
            if isinstance(high_vol_raw, dict)
            else None
        )

        vol_expansion_score = self._extract_score(
            rating, "spot_indicators", "波动率扩张"
        )
        bollinger_score = self._extract_score(
            rating, "spot_indicators", "布林带压缩"
        )

        total_score = rating.get("total_score", 0)
        resonance_label = rating.get("resonance_label", "")

        # ── 2. 计算 excess_pct 和 safety_margin ──
        excess_pct: Optional[float] = None
        safety_margin: Optional[float] = None

        if gamma_wall is not None and gamma_wall > 0:
            excess_pct = (spot_price - gamma_wall) / gamma_wall

        if zero_gamma is not None and spot_price > 0:
            safety_margin = (spot_price - zero_gamma) / spot_price

        # ── 3. 硬性筛选 ──
        filter_reasons: List[str] = []

        if total_score < self.min_total_score:
            filter_reasons.append(
                f"综合分({total_score}) < 最低阈值({self.min_total_score})"
            )

        if gamma_wall is None:
            filter_reasons.append("γ Wall 数据缺失")
        elif spot_price <= gamma_wall:
            filter_reasons.append(
                f"收盘价({spot_price:.2f}) <= γ Wall({gamma_wall:.2f})"
            )

        if excess_pct is not None and excess_pct > 0.15:
            filter_reasons.append(
                f"突破幅度({excess_pct*100:.1f}%) > 15%，追高风险"
            )

        if gex_regime != "正Gamma":
            filter_reasons.append(
                f"GEX环境为「{gex_regime}」，非正Gamma"
            )

        if net_delta is None or net_delta <= 0:
            filter_reasons.append(
                f"Delta方向({net_delta}) <= 0，聪明钱未看涨"
            )

        if filter_reasons:
            return BullScreeningResult(
                passed_filter=False,
                filter_reasons=filter_reasons,
                excess_pct=round(excess_pct, 4) if excess_pct is not None else None,
                safety_margin=round(safety_margin, 4) if safety_margin is not None else None,
            )

        # ── 4. 构建 context 并运行 10 维度引擎 ──
        bull_context: Dict[str, Any] = {
            "excess_pct": excess_pct or 0.0,
            "net_delta": net_delta,
            "pc_ratio": pc_ratio,
            "iv_skew": iv_skew,
            "resonance_label": resonance_label,
            "rs": rs,
            "iv_hv_ratio": iv_hv_ratio,
            "consecutive_volume_burst": bool(consecutive_burst),
            "vol_5d_20d": vol_5d_20d,
            "vol_expansion_score": vol_expansion_score,
            "bollinger_score": bollinger_score,
            "active_dte": active_dte,
        }

        dimensions, _ = self.engine.run(bundle, initial_context=bull_context)

        raw_score = sum(ind.score for ind in dimensions.values() if ind.available)

        # ── 5. 扣分项 ──
        deduction = 0
        deduction_reason = ""
        if daily_return is not None:
            if daily_return > 0.10:
                deduction = 2
                deduction_reason = f"当日涨幅{daily_return*100:.1f}%>10%，扣2分"
            elif daily_return > 0.05:
                deduction = 1
                deduction_reason = f"当日涨幅{daily_return*100:.1f}%>5%，扣1分"

        bull_score = max(raw_score - deduction, 0)

        # ── 6. 梯队分级 ──
        if bull_score >= 20:
            tier = "🥇 一梯队"
        elif bull_score >= 15:
            tier = "🥈 二梯队"
        elif bull_score >= 10:
            tier = "🥉 三梯队"
        else:
            tier = "未入梯队"

        return BullScreeningResult(
            passed_filter=True,
            bull_score=bull_score,
            raw_score=raw_score,
            deduction=deduction,
            deduction_reason=deduction_reason,
            dimensions=dimensions,
            excess_pct=round(excess_pct, 4) if excess_pct is not None else None,
            safety_margin=round(safety_margin, 4) if safety_margin is not None else None,
            tier=tier,
        )

    # ── 辅助提取方法 ──

    @staticmethod
    def _extract_gamma_value(rating: dict, name: str) -> Optional[float]:
        ind = rating.get("gamma_indicators", {}).get(name, {})
        val = ind.get("raw_value")
        if val is None or ind.get("available") is False:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_gamma_signal(rating: dict, name: str) -> str:
        ind = rating.get("gamma_indicators", {}).get(name, {})
        return ind.get("signal", "不可用")

    @staticmethod
    def _extract_raw_value(
        rating: dict, category: str, name: str
    ) -> Any:
        ind = rating.get(category, {}).get(name, {})
        return ind.get("raw_value")

    @staticmethod
    def _extract_score(
        rating: dict, category: str, name: str
    ) -> int:
        ind = rating.get(category, {}).get(name, {})
        return ind.get("score", 0)
