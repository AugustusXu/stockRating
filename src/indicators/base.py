"""
指标抽象基类 — 所有指标插件必须继承 BaseIndicator 并实现 meta() 和 compute()。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..models import IndicatorResult, MarketDataBundle


@dataclass
class IndicatorMeta:
    """指标的自描述元数据。"""

    name: str
    """指标名称，如 "P/C Ratio"。"""

    category: str
    """指标分类: "option" | "spot" | "gamma" | "internal"。"""

    max_score: int = 0
    """该指标的理论最高分。"""

    participates_in_voting: bool = False
    """是否参与方向投票（看涨/看跌统计）。"""

    description: str = ""
    """可选的简短说明。"""


class BaseIndicator(ABC):
    """所有指标的抽象基类。"""

    @abstractmethod
    def meta(self) -> IndicatorMeta:
        """返回指标的元数据。"""
        ...

    @abstractmethod
    def compute(
        self,
        bundle: MarketDataBundle,
        context: Dict[str, Any],
    ) -> IndicatorResult:
        """
        计算指标并返回结果。

        Args:
            bundle: 原始市场数据包。
            context: 共享的中间计算结果字典，由 IndicatorEngine 管理。
                     指标可以从 context 读取自己声明的 dependencies，
                     也可以将自己 provide 的键写入 context。

        Returns:
            填充好的 IndicatorResult 实例。
        """
        ...

    def dependencies(self) -> List[str]:
        """
        声明该指标依赖的 context 键列表。
        IndicatorEngine 会据此做拓扑排序，确保依赖先于自身执行。
        默认无依赖。
        """
        return []

    def provide(self) -> List[str]:
        """
        声明该指标会往 context 中写入的键列表。
        用于构建依赖图。默认不提供。
        """
        return []
