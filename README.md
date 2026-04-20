# Stock Rating System

基于期权与现货多维信号的美股异动评分系统。

本项目将每个标的在同一交易日内拆分为三部分评分：

- 期权维度评分（最高 21 分）
- 现货维度评分（最高 9 分）
- 期现共振加分（最高 5 分）

综合分计算：

- 综合分 = 期权分 + 现货分 + 共振加分
- 理论满分 35 分

项目核心目标不是“预测精确涨跌幅”，而是量化“异动强度 + 方向一致性”，用于盘后复盘、标的筛选与交易前信号验证。

## 功能特性

- 自动拉取行情与期权链（默认 yfinance，akshare 作为现货兜底）
- 计算期权 7 大指标与现货 6 大指标
- 基于投票机制输出方向信号（强看涨/看涨/多空博弈/看跌等）
- 自动计算期现共振（HOT/WARM/方向矛盾）并加分
- 支持单标的、批量标的评分
- 支持 Gamma 四指标外部注入（GEX净值、GEX环境、γ Wall、Zero Gamma）
- 当 Gamma 数据缺失时自动退化为说明模式（不会报错中断）

## 评分体系（与 ratingDetails 对齐）

### 1) 期权维度（满分 21）

- Vol/OI 极端：1/3/5
- P/C Ratio：1/3
- IV Skew 反转：3
- 多行权价联动：2
- Delta 加权方向：3
- IV/HV 比率：2/3
- 末日期权效应：2

### 2) 现货维度（满分 9）

- 高位放量：3
- 强阳柱：1
- RS vs SPY：1/2
- 连续放量>=3天：1
- 布林带压缩：1
- 波动率扩张：1

### 3) 交叉共振（满分 5）

- HOT（真共振）：+5
- WARM（半共振）：+3
- 方向矛盾：+1

说明：共振触发前提为期权分 >= 3 且现货分 >= 3。

## 项目结构

```text
.
├─ pyproject.toml
├─ ratingDetails.md
├─ test.ipynb
└─ src/
   ├─ __init__.py
   ├─ api.py
   ├─ config.py
   ├─ data_loader.py
   ├─ features.py
   ├─ models.py
   └─ scoring.py
```

## 安装

### 环境要求

- Python >= 3.10

### 安装依赖

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
        "gamma_wall": 210,
        "zero_gamma": 198,
        "source": "manual-input",
    },
)

print(result["ticker"], result["total_score"], result["overall_direction"])
print(result["resonance_label"], result["warnings"])
```

### 2) 批量评分

```python
from src import get_bulk_stock_ratings

tickers = ["AAPL", "MSFT", "NVDA"]

gamma_inputs_by_ticker = {
    "AAPL": {"gex_net": 1250000, "gex_regime": "正Gamma", "gamma_wall": 210, "zero_gamma": 198},
    "MSFT": {"gex_net": -860000, "gex_regime": "负Gamma", "gamma_wall": 420, "zero_gamma": 430},
}

results = get_bulk_stock_ratings(
    tickers=tickers,
    gamma_inputs_by_ticker=gamma_inputs_by_ticker,
)

for item in results:
    print(item.get("ticker"), item.get("total_score"), item.get("overall_direction"), item.get("error"))
```

### 3) 不传 Gamma 数据（说明模式）

```python
from src import get_stock_rating

result = get_stock_rating("TSLA")
print(result["gamma_indicators"])            # available=False + explain
print(result["unavailable_indicators"])      # 不可用指标原因
```

## 返回结果说明

评分结果为字典，关键字段如下：

- ticker: 标的代码
- as_of: 评分日期
- option_indicators: 期权维度指标明细（含 raw_value/score/signal/explain/available）
- spot_indicators: 现货维度指标明细
- gamma_indicators: Gamma 指标明细（支持说明模式）
- option_score: 期权总分
- spot_score: 现货总分
- resonance_bonus: 共振加分
- total_score: 综合分
- option_direction: 期权方向标签
- spot_direction: 现货方向标签
- overall_direction: 总体方向结论
- resonance_label: HOT / WARM / 方向矛盾 / 空
- warnings: 运行期提示（例如数据不足、共振解释）
- unavailable_indicators: 不可用指标说明

## 方向判定规则

方向来自投票机制（而非总分高低）：

- 期权方向投票：P/C Ratio + IV Skew + Delta加权方向
- 现货方向投票：基于现货各指标 signal 统计

常见输出包括：

- 强看涨 / 看涨 / 偏看涨(有分歧)
- 强看跌 / 看跌 / 偏看跌(有分歧)
- 多空博弈 / 中性

## 数据源与边界

- 现货与期权链：yfinance（现货支持 akshare 兜底）
- 基准：SPY（用于 RS vs SPY）
- Gamma 四指标：当前不在项目内实时计算，需要外部传入

这意味着：

- 若你有券商/数据终端的 GEX 与 Gamma Wall 数据，可直接注入后得到完整评分
- 若没有 Gamma 输入，系统仍可输出可解释的期权+现货评分

## 常见问题

### Q1: 为什么有时期权分为 0？

可能原因：

- 标的无可用期权链
- 期权链字段缺失或成交量/持仓数据不足

系统会在 warnings 中给出提示。

### Q2: 为什么综合分高但方向不是“看涨”？

综合分衡量的是“异动强度”，方向由投票决定。
高分 + 看跌或多空博弈是可能且常见的。

### Q3: Gamma 指标为什么显示不可用？

当未传入 `gamma_inputs`，或字段无法解析时，Gamma 指标会进入说明模式并返回原因。

## 开发与测试

运行测试：

```bash
pytest -q
```

## 免责声明

本项目仅用于量化研究与策略开发参考，不构成任何投资建议。市场有风险，交易需结合风控与独立判断。
