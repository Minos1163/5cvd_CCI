from __future__ import annotations

from src.core.models import Candle, IndicatorSnapshot
from src.indicators.atr import atr
from src.indicators.boll import bollinger
from src.indicators.cci import cci
from src.indicators.cvd import cumulative_cvd, cvd_delta
from src.indicators.macd import macd
from src.indicators.rsi import rsi


def compute_indicator_snapshot(candles: list[Candle]) -> IndicatorSnapshot:
    if not candles:
        raise ValueError("candles must not be empty")

    last = candles[-1]
    closes = [candle.close for candle in candles]
    macd_values = macd(closes)
    boll_values = bollinger(closes)
    cvd_values = cumulative_cvd(candles)

    return IndicatorSnapshot(
        symbol=last.symbol,
        timeframe=last.timeframe,
        close_time=last.close_time,
        macd=macd_values[0] if macd_values else None,
        macd_signal=macd_values[1] if macd_values else None,
        macd_hist=macd_values[2] if macd_values else None,
        cci=cci(candles),
        rsi=rsi(closes),
        boll_mid=boll_values[0] if boll_values else None,
        boll_upper=boll_values[1] if boll_values else None,
        boll_lower=boll_values[2] if boll_values else None,
        atr=atr(candles),
        cvd=cvd_values[-1] if cvd_values else None,
        cvd_delta=cvd_delta(last.taker_buy_volume, last.volume),
    )
