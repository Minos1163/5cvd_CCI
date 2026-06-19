from __future__ import annotations


TIMEFRAME_SECONDS = {
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
}


def timeframe_seconds(timeframe: str) -> int:
    return TIMEFRAME_SECONDS[timeframe]
