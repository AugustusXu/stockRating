BENCHMARK_TICKER = "SPY"
HISTORY_LOOKBACK_PERIOD = "1y"
MAX_OPTION_EXPIRIES = 3
RISK_FREE_RATE = 0.04
TRADING_DAYS_PER_YEAR = 252

OPTION_INDICATOR_NAMES = [
    "Vol/OI极端",
    "P/C Ratio",
    "IV Skew反转",
    "多行权价联动",
    "Delta加权方向",
    "IV/HV比率",
    "末日期权效应",
]

SPOT_INDICATOR_NAMES = [
    "高位放量",
    "强阳柱",
    "RS vs SPY",
    "连续放量>=3天",
    "布林带压缩",
    "波动率扩张",
]

GAMMA_INDICATOR_NAMES = [
    "GEX净值",
    "GEX环境",
    "γ Wall",
    "Zero Gamma",
]

UNAVAILABLE_INDICATORS = {
    "γ Wall": "缺少可用Gamma数据，无法定位最大Gamma暴露行权价。",
    "GEX净值": "缺少可用Gamma数据，无法计算净Gamma Exposure。",
    "GEX环境": "缺少净Gamma结果，无法判定正/负Gamma环境。",
    "Zero Gamma": "Gamma曲线未形成有效翻转或数据不足，无法估算Zero Gamma。",
}
