BENCHMARK_TICKER = "SPY"
HISTORY_LOOKBACK_PERIOD = "1y"
MAX_OPTION_EXPIRIES = 3
RISK_FREE_RATE = 0.04
TRADING_DAYS_PER_YEAR = 252


UNAVAILABLE_INDICATORS = {
    "γ Wall": "缺少可用Gamma数据，无法定位最大Gamma暴露行权价。",
    "GEX净值": "缺少可用Gamma数据，无法计算净Gamma Exposure。",
    "GEX环境": "缺少净Gamma结果，无法判定正/负Gamma环境。",
    "Zero Gamma": "Gamma曲线未形成有效翻转或数据不足，无法估算Zero Gamma。",
}
