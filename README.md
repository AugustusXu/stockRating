# Stock Rating System

基于期权与现货多维信号的美股异动评分系统。

项目核心目标不是"预测精确涨跌幅"，而是量化"异动强度 + 方向一致性"，用于盘后复盘、标的筛选与交易前信号验证。

## 功能特性

- **插件化指标体系**：每个指标独立为一个 Python 模块，通过 `IndicatorEngine` 统一注册和调度
- **自动拉取行情与期权链**：默认 yfinance，akshare 作为现货兜底
- **三维度评分**：期权 7 大指标（满分 21）+ 现货 6 大指标（满分 9）+ 期现共振（满分 5），理论满分 35
- **方向投票机制**：P/C Ratio、IV Skew、Delta 加权方向三票制，输出方向标签（强看涨/看涨/多空博弈/看跌等）
- **正股看涨筛选**：5 条硬性筛选 + 10 维度评分，产出梯队分级与安全边际
- **Gamma 外部注入**：支持 GEX净值/GEX环境/γ Wall/Zero Gamma 外部传入，缺失时自动退化为说明模式
- **运行时指标开关**：支持 `engine.disable()` / `engine.enable()` 动态启用/禁用任意指标

## 评分体系

> 详细规则参见 [ratingDetails.md](ratingDetails.md)

### 期权维度（满分 21）

| 指标 | 分值 | 说明 |
|------|------|------|
| Vol/OI 极端 | 1/3/5 | 最大成交量/持仓量比值分档 |
| P/C Ratio | 1/3 | 看跌/看涨成交量比率 |
| IV Skew 反转 | 3 | Call IV - Put IV |
| 多行权价联动 | 2 | Vol/OI≥3 的行权价个数 |
| Delta 加权方向 | 3 | BSM Delta × Volume 加权汇总 |
| IV/HV 比率 | 2/3 | ATM IV 与 20 日历史波动率比值 |
| 末日期权效应 | 2 | 最活跃合约 DTE ≤ 5 |

### 现货维度（满分 9）

| 指标 | 分值 | 说明 |
|------|------|------|
| 高位放量 | 3 | 近 252 日高点 75% 以上 + 5 日均量 ≥ 20 日均量 1.5 倍 |
| 强阳柱 | 1 | 当日涨幅 > 5% |
| RS vs SPY | 1/2 | 20 日超额收益 |
| 连续放量≥3天 | 1 | 近 3 天成交量均超 20 日均量 1.3 倍 |
| 布林带压缩 | 1 | 布林带宽度 < 3% |
| 波动率扩张 | 1 | HV(10d) > HV(50d) |

### 交叉共振（满分 5）

| 类型 | 加分 | 触发条件 |
|------|------|----------|
| 🔥 真共振 HOT | +5 | 期权分≥3 + 现货分≥3 + 方向一致 |
| ⚡ 半共振 WARM | +3 | 期权分≥3 + 现货分≥3 + 一方不明确 |
| 方向矛盾 | +1 | 期权分≥3 + 现货分≥3 + 方向相反 |

### 正股看涨筛选（10 维度，理论最高 ~31 分）

通过 5 条硬性筛选（综合分 ≥ 8、收盘价 > γ Wall、突破 ≤ 15%、正 Gamma、Delta > 0）后，从 10 个维度打分：

| # | 维度 | 分值 |
|---|------|------|
| ① | γ Wall 突破位置 | 1/3/4 |
| ② | Delta 方向强度 | 1/2/3/4 |
| ③ | P/C Ratio | 1/2/3/4 |
| ④ | IV Skew 反转 | 2/3/4 |
| ⑤ | 期现共振 | 2/4 |
| ⑥ | RS% 相对强度 | 1/2/3 |
| ⑦ | IV/HV 波动定价 | 1/2 |
| ⑧ | 资金持续性 | 1/2 |
| ⑨ | 波动率状态 | 1+1 |
| ⑩ | 机构布局期限 | 1/2 |

**扣分项**：当日涨幅 > 10% 扣 2 分，> 5% 扣 1 分

**梯队分级**：🥇 一梯队 ≥ 20分 / 🥈 二梯队 15-19分 / 🥉 三梯队 10-14分

## 项目结构

```text
.
├── pyproject.toml
├── ratingDetails.md           # 评分体系与指标详细说明
├── test.ipynb                 # 交互式测试
└── src/
    ├── __init__.py            # 公共 API 导出
    ├── api.py                 # StockRatingService 入口
    ├── bull_screening.py      # 正股看涨筛选器
    ├── config.py              # 全局配置常量
    ├── data_loader.py         # yfinance / akshare 数据加载
    ├── models.py              # 数据模型（IndicatorResult, RatingResult 等）
    ├── scoring.py             # 投票、共振、方向合并
    ├── utils.py               # 结果展示辅助函数
    └── indicators/            # 插件化指标体系
        ├── __init__.py        # default_engine() 工厂函数
        ├── base.py            # BaseIndicator 抽象基类 + IndicatorMeta
        ├── engine.py          # IndicatorEngine（注册/拓扑排序/执行/enable/disable）
        ├── context_providers.py  # 数据预处理器（OptionFrame, SpotBase, AtmIv）
        ├── option/            # 期权指标（7 个）
        │   ├── vol_oi.py          # Vol/OI 极端
        │   ├── pc_ratio.py        # P/C Ratio
        │   ├── iv_skew.py         # IV Skew 反转
        │   ├── multi_strike.py    # 多行权价联动
        │   ├── delta_direction.py # Delta 加权方向
        │   ├── iv_hv.py           # IV/HV 比率
        │   └── short_dte.py       # 末日期权效应
        ├── spot/              # 现货指标（6 个）
        │   ├── high_volume.py         # 高位放量
        │   ├── strong_candle.py       # 强阳柱
        │   ├── relative_strength.py   # RS vs SPY
        │   ├── consecutive_volume.py  # 连续放量≥3天
        │   ├── bollinger_squeeze.py   # 布林带压缩
        │   └── vol_expansion.py       # 波动率扩张
        ├── gamma/             # Gamma 指标（4 个）
        │   ├── gex_net.py         # GEX 净值
        │   ├── gex_regime.py      # GEX 环境
        │   ├── gamma_wall.py      # γ Wall
        │   └── zero_gamma.py      # Zero Gamma
        └── bull/              # 正股看涨筛选维度（10 个）
            ├── gamma_wall_breakout.py   # ① γ Wall 突破位置
            ├── delta_strength.py        # ② Delta 方向强度
            ├── pc_ratio_bull.py         # ③ P/C Ratio
            ├── iv_skew_bull.py          # ④ IV Skew 反转
            ├── resonance_bull.py        # ⑤ 期现共振
            ├── rs_bull.py               # ⑥ RS% 相对强度
            ├── iv_hv_bull.py            # ⑦ IV/HV 波动定价
            ├── funding_persistence.py   # ⑧ 资金持续性
            ├── volatility_state.py      # ⑨ 波动率状态
            └── institutional_dte.py     # ⑩ 机构布局期限
```

## 安装

**环境要求**：Python >= 3.10

```bash
pip install -e .
```

如需测试依赖：

```bash
pip install -e .[dev]
```

## 快速开始

### 1) 单标的评分

```python
from src import get_stock_rating

result = get_stock_rating(
    ticker="AAPL",
    gamma_inputs={
        "gex_net": 1250000,
        "gex_regime": "正Gamma",
        "gamma_wall": 278,
        "zero_gamma": 265,
        "source": "barchart",
    },
)

print(result["ticker"], result["total_score"], result["overall_direction"])
print(result["resonance_label"])
```

### 2) 批量评分

```python
from src import get_bulk_stock_ratings

results = get_bulk_stock_ratings(
    tickers=["AAPL", "MSFT", "NVDA"],
    gamma_inputs_by_ticker={
        "AAPL": {"gex_net": 1250000, "gex_regime": "正Gamma", "gamma_wall": 278, "zero_gamma": 265},
        "MSFT": {"gex_net": -860000, "gex_regime": "负Gamma", "gamma_wall": 420, "zero_gamma": 430},
    },
)

for item in results:
    print(item.get("ticker"), item.get("total_score"), item.get("overall_direction"))
```

### 3) 正股看涨筛选

每次调用 `get_stock_rating()` 返回结果中自动包含 `bull_screening` 字段：

```python
result = get_stock_rating(
    "AAPL",
    gamma_inputs={
        "gex_net": 5000000,
        "gex_regime": "正Gamma",
        "gamma_wall": 278,
        "zero_gamma": 265,
    },
)

bull = result["bull_screening"]
if bull["passed_filter"]:
    print(f"看涨分: {bull['bull_score']}  梯队: {bull['tier']}")
    print(f"安全边际: {bull['safety_margin']:.1%}  突破%: {bull['excess_pct']:.1%}")
    for name, dim in bull["dimensions"].items():
        print(f"  {name}: {dim['score']}分 ({dim['signal']})")
else:
    print("未通过硬性筛选:", bull["filter_reasons"])
```

### 4) 不传 Gamma 数据（说明模式）

```python
result = get_stock_rating("TSLA")
print(result["gamma_indicators"])        # available=False + explain
print(result["unavailable_indicators"])  # 不可用指标原因
# bull_screening 也会因缺少 γ Wall 而不通过筛选
```

### 5) 运行时启用/禁用指标

```python
from src.api import StockRatingService

svc = StockRatingService()

# 禁用基础指标
svc.engine.disable("P/C Ratio", "布林带压缩")
result = svc.get_stock_rating("AAPL")
# P/C Ratio 和布林带压缩不再出现在结果中

# 禁用看涨筛选维度
svc.bull_screener.engine.disable("IV/HV波动定价(看涨)")

# 查看当前所有指标及其启用状态
svc.engine.list_indicators()
svc.bull_screener.engine.list_indicators()

# 全部恢复
svc.engine.enable_all()
svc.bull_screener.engine.enable_all()
```

### 6) 自定义指标

每个指标是一个继承 `BaseIndicator` 的独立类：

```python
from src.indicators.base import BaseIndicator, IndicatorMeta
from src.models import IndicatorResult, MarketDataBundle

class MyCustomIndicator(BaseIndicator):
    def meta(self):
        return IndicatorMeta(
            name="自定义指标",
            category="spot",           # "option" / "spot" / "gamma" / "bull"
            max_score=3,
            participates_in_voting=True,
        )

    def dependencies(self):
        return ["spot_close"]          # 声明依赖的 context 键

    def compute(self, bundle, context):
        close = context.get("spot_close")
        # ... 你的计算逻辑 ...
        return IndicatorResult(name="自定义指标", raw_value=..., score=..., signal=...)
```

注册到引擎：

```python
from src.api import StockRatingService

svc = StockRatingService()
svc.engine.register(MyCustomIndicator())
```

## 返回结果说明

### 基础评分字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `ticker` | str | 标的代码 |
| `as_of` | str | 评分日期 |
| `option_indicators` | dict | 期权指标明细（含 raw_value/score/signal/explain/available） |
| `spot_indicators` | dict | 现货指标明细 |
| `gamma_indicators` | dict | Gamma 指标明细（支持说明模式） |
| `option_score` | int | 期权总分 |
| `spot_score` | int | 现货总分 |
| `resonance_bonus` | int | 共振加分 |
| `total_score` | int | 综合分 = 期权 + 现货 + 共振 |
| `option_direction` | str | 期权方向标签 |
| `spot_direction` | str | 现货方向标签 |
| `overall_direction` | str | 总体方向结论 |
| `resonance_label` | str | HOT / WARM / 方向矛盾 / 空 |
| `warnings` | list | 运行期提示 |
| `unavailable_indicators` | dict | 不可用指标及原因 |

### 正股看涨筛选字段（`bull_screening`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `passed_filter` | bool | 是否通过 5 条硬性筛选 |
| `filter_reasons` | list | 未通过的具体原因 |
| `bull_score` | int | 看涨分（扣分后） |
| `raw_score` | int | 10 维度原始总分 |
| `deduction` | int | 扣分值 |
| `deduction_reason` | str | 扣分原因（追高惩罚） |
| `dimensions` | dict | 10 个维度的明细 |
| `excess_pct` | float | 突破 γ Wall 的百分比 |
| `safety_margin` | float | 收盘价到 Zero Gamma 的距离百分比 |
| `tier` | str | 梯队分级 |

## 架构设计

### 指标插件体系

每个指标通过 `BaseIndicator` 抽象基类声明：

- **`meta()`** — 名称、分类、最高分、是否参与投票
- **`dependencies()`** — 依赖的 context 键（显式声明依赖关系）
- **`provide()`** — 向 context 写入的键
- **`compute(bundle, context)`** — 计算逻辑

`IndicatorEngine` 基于 `dependencies()` / `provide()` 做拓扑排序，确保数据预处理器先于依赖它的指标执行。

### Context Provider

3 个 internal Provider 不产生评分，只向 context 注入共享中间量：

| Provider | 写入的 context 键 |
|----------|------------------|
| `OptionFrameProvider` | `option_frame` |
| `SpotBaseProvider` | `spot_close`, `spot_volume`, `daily_return`, `high_252` |
| `AtmIvProvider` | `call_iv`, `put_iv`, `atm_iv`, `hv20` |

## 数据源与边界

- **现货与期权链**：yfinance（现货支持 akshare 兜底）
- **基准**：SPY（用于 RS vs SPY）
- **Gamma 四指标**：需外部传入（`barchart.com → stock → option → Gamma Exposure`）

## 常见问题

### Q1: 为什么有时期权分为 0？

可能原因：标的无可用期权链，或期权链字段缺失/成交量不足。系统会在 `warnings` 中给出提示。

### Q2: 为什么综合分高但方向不是"看涨"？

综合分衡量的是"异动强度"，方向由投票决定。高分 + 看跌或多空博弈是可能且常见的。

### Q3: Gamma 指标为什么显示不可用？

未传入 `gamma_inputs` 或字段无法解析时，Gamma 指标进入说明模式。正股看涨筛选也会因此不通过硬性筛选。

### Q4: 如何新增一个自定义指标？

创建一个继承 `BaseIndicator` 的类，实现 `meta()` 和 `compute()` 方法，然后调用 `engine.register()` 注册即可。参见"自定义指标"章节。

## 开发与测试

```bash
pytest -q
```

## 免责声明

本项目仅用于量化研究与策略开发参考，不构成任何投资建议。市场有风险，交易需结合风控与独立判断。
