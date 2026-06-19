from __future__ import annotations


DEFAULT_INDICATOR_PARAMS = {
    "MACD": {"fast": 12, "slow": 26, "signal": 9},
    "RSI": {"period": 14},
    "CCI": {"period": 20},
    "BOLL": {"period": 20, "std": 2.0},
    "ATR": {"period": 14},
    "CVD": {},
}

INDICATOR_RESPONSIBILITIES = {
    "MACD": "trend",
    "RSI": "pullback",
    "CCI": "strength",
    "BOLL": "structure",
    "CVD": "fund_flow",
    "ATR": "risk",
}

INDICATOR_PRIORITY = ("MACD", "CVD", "RSI", "CCI", "BOLL")


def validate_indicator_usage(indicator: str, usage: str) -> tuple[bool, str]:
    key = indicator.upper()
    responsibility = INDICATOR_RESPONSIBILITIES.get(key)
    if responsibility is None:
        return False, f"unknown indicator: {indicator}"
    if key == "ATR" and usage == "direction":
        return False, "ATR is reserved for risk and must not be used for direction"
    return True, f"{key} allowed for {usage}"


def classify_rsi(value: float) -> str:
    if value > 70:
        return "overheated"
    if value < 30:
        return "oversold"
    if 40 <= value <= 60:
        return "range"
    return "neutral"


def classify_cci(value: float) -> str:
    if value > 100:
        return "strong"
    if value < -100:
        return "weak"
    return "neutral"
