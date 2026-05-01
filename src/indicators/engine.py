"""
IndicatorEngine — 指标注册中心与执行引擎。

职责：
1. 注册指标插件
2. 运行时启用/禁用指标
3. 按依赖关系拓扑排序
4. 依次执行每个指标的 compute()
5. 汇总投票（看涨/看跌）
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from .base import BaseIndicator
from ..models import IndicatorResult, MarketDataBundle


class IndicatorEngine:
    """指标注册中心 & 执行引擎。"""

    def __init__(self) -> None:
        self._indicators: List[BaseIndicator] = []
        self._meta_cache: Dict[str, str] = {}  # name -> category
        self._disabled: Set[str] = set()  # 运行时禁用的指标名称

    # ── 注册 ──

    def register(self, indicator: BaseIndicator) -> "IndicatorEngine":
        """注册单个指标，支持链式调用。"""
        self._indicators.append(indicator)
        m = indicator.meta()
        self._meta_cache[m.name] = m.category
        return self

    def register_all(self, indicators: List[BaseIndicator]) -> "IndicatorEngine":
        """批量注册。"""
        for ind in indicators:
            self.register(ind)
        return self

    # ── 运行时启用/禁用 ──

    def disable(self, *names: str) -> "IndicatorEngine":
        """运行时禁用指定名称的指标（不影响 internal 类的 provider）。"""
        self._disabled.update(names)
        return self

    def enable(self, *names: str) -> "IndicatorEngine":
        """重新启用之前禁用的指标。"""
        self._disabled -= set(names)
        return self

    def enable_all(self) -> "IndicatorEngine":
        """启用所有指标（清空禁用列表）。"""
        self._disabled.clear()
        return self

    @property
    def disabled_indicators(self) -> Set[str]:
        """返回当前被禁用的指标名称集合。"""
        return set(self._disabled)

    # ── 查询 ──

    def get_category(self, name: str) -> str:
        """根据指标名称返回其分类。"""
        return self._meta_cache.get(name, "unknown")

    def list_indicators(self) -> List[Dict[str, Any]]:
        """列出所有已注册的非 internal 指标及其启用状态。"""
        result = []
        for ind in self._indicators:
            m = ind.meta()
            if m.category == "internal":
                continue
            result.append(
                {
                    "name": m.name,
                    "category": m.category,
                    "max_score": m.max_score,
                    "participates_in_voting": m.participates_in_voting,
                    "enabled": m.name not in self._disabled,
                }
            )
        return result

    # ── 执行 ──

    def run(
        self,
        bundle: MarketDataBundle,
        initial_context: Dict[str, Any] | None = None,
    ) -> Tuple[Dict[str, IndicatorResult], Tuple[int, int]]:
        """
        按依赖顺序执行所有已注册且未被禁用的指标。

        Returns:
            (indicators_dict, (bull_votes, bear_votes))
            - indicators_dict 中不包含 category=="internal" 的条目
        """
        context: Dict[str, Any] = dict(initial_context or {})
        results: Dict[str, IndicatorResult] = {}
        bull_votes, bear_votes = 0, 0

        ordered = self._topological_sort()

        for indicator in ordered:
            m = indicator.meta()

            # internal provider 始终执行（它们只准备 context，不产生输出）
            # 非 internal 且被禁用的指标跳过
            if m.category != "internal" and m.name in self._disabled:
                continue

            try:
                result = indicator.compute(bundle, context)
            except Exception as exc:
                result = IndicatorResult(
                    name=m.name,
                    raw_value=None,
                    score=0,
                    signal="中性",
                    explain=f"计算异常: {exc}",
                    available=False,
                )

            # 跳过 internal（纯预处理器），不暴露给最终结果
            if m.category != "internal":
                results[m.name] = result

            # 投票统计
            if m.participates_in_voting and result.available:
                if "看涨" in result.signal and "看跌" not in result.signal:
                    bull_votes += 1
                elif "看跌" in result.signal and "看涨" not in result.signal:
                    bear_votes += 1

        return results, (bull_votes, bear_votes)

    # ── 拓扑排序 ──

    def _topological_sort(self) -> List[BaseIndicator]:
        """
        基于 dependencies() / provide() 做拓扑排序。
        无法满足的依赖会被忽略（指标内部自行处理 context 缺失）。
        """
        # 建立 key -> indicator 的 provide 映射
        provider_map: Dict[str, BaseIndicator] = {}
        for ind in self._indicators:
            for key in ind.provide():
                provider_map[key] = ind

        # 建邻接表（edge: 被依赖者 -> 依赖者）
        in_degree: Dict[int, int] = {id(ind): 0 for ind in self._indicators}
        adj: Dict[int, List[int]] = {id(ind): [] for ind in self._indicators}
        id_to_ind: Dict[int, BaseIndicator] = {
            id(ind): ind for ind in self._indicators
        }

        for ind in self._indicators:
            for dep_key in ind.dependencies():
                provider = provider_map.get(dep_key)
                if provider is not None and id(provider) != id(ind):
                    adj[id(provider)].append(id(ind))
                    in_degree[id(ind)] += 1

        # Kahn 算法
        queue = [iid for iid, deg in in_degree.items() if deg == 0]
        ordered: List[BaseIndicator] = []

        while queue:
            current = queue.pop(0)
            ordered.append(id_to_ind[current])
            for neighbor in adj[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 如果有循环依赖导致部分节点未排入，追加到末尾
        sorted_ids = {id(ind) for ind in ordered}
        for ind in self._indicators:
            if id(ind) not in sorted_ids:
                ordered.append(ind)

        return ordered
