from __future__ import annotations

from src.core.models import Candle, IndicatorSnapshot
from src.data.data_contract import IndicatorResult, MarketCandle, market_candle_to_candle
from src.indicators.atr import atr
from src.indicators.boll import bollinger
from src.indicators.cci import cci
from src.indicators.cvd import cumulative_cvd, cvd_delta
from src.indicators.ema import bars_since_cross, ema, normalized_ema_slope
from src.indicators.indicator_spec import quality_allows_signal_use
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
    ema_9_series = ema(closes, 9)
    ema_21_series = ema(closes, 21)
    ema_50_series = ema(closes, 50)
    ema_200_series = ema(closes, 200)
    ema_9 = ema_9_series[-1] if ema_9_series else None
    ema_21 = ema_21_series[-1] if ema_21_series else None
    ema_50 = ema_50_series[-1] if ema_50_series else None
    ema_200 = ema_200_series[-1] if ema_200_series else None

    return IndicatorSnapshot(
        symbol=last.symbol,
        timeframe=last.timeframe,
        close_time=last.close_time,
        macd=macd_values[0] if macd_values else None,
        macd_signal=macd_values[1] if macd_values else None,
        macd_hist=macd_values[2] if macd_values else None,
        cci=cci(candles),
        rsi=rsi(closes),
        ema_9=ema_9,
        ema_21=ema_21,
        ema_50=ema_50,
        ema_200=ema_200,
        ema50_slope=normalized_ema_slope(ema_50_series, 5) if ema_50_series else None,
        ema9_21_gap=(ema_9 - ema_21) / ema_21 if ema_9 is not None and ema_21 not in (None, 0) else None,
        bars_since_ema50_cross=bars_since_cross(closes[-len(ema_50_series) :], ema_50_series) if ema_50_series else None,
        bars_since_ema200_cross=bars_since_cross(closes[-len(ema_200_series) :], ema_200_series) if ema_200_series else None,
        boll_mid=boll_values[0] if boll_values else None,
        boll_upper=boll_values[1] if boll_values else None,
        boll_lower=boll_values[2] if boll_values else None,
        atr=atr(candles),
        cvd=cvd_values[-1] if cvd_values else None,
        cvd_delta=cvd_delta(last.taker_buy_volume, last.volume),
    )


def compute_indicator_results(candles: list[MarketCandle]) -> list[IndicatorResult]:
    if not candles:
        raise ValueError("candles must not be empty")
    _validate_market_candles_for_indicator_results(candles)
    core_candles = [market_candle_to_candle(item) for item in candles]
    snapshot = compute_indicator_snapshot(core_candles)
    closes = [item.close for item in core_candles]
    quality_flag = _combined_quality_flag(candles)

    return [
        _build_macd_result(snapshot, closes, quality_flag),
        _build_cci_result(snapshot, core_candles, quality_flag),
        _build_boll_result(snapshot, closes, quality_flag),
        _build_ema_result(snapshot, closes, quality_flag),
        _build_cvd_result(snapshot, core_candles, quality_flag),
        _build_atr_result(snapshot, core_candles, quality_flag),
    ]


def _validate_market_candles_for_indicator_results(candles: list[MarketCandle]) -> None:
    first_symbol = candles[0].symbol
    first_timeframe = candles[0].timeframe
    previous_open_time = -1
    for candle in candles:
        if candle.symbol != first_symbol:
            raise ValueError("indicator candles must use one symbol")
        if candle.timeframe != first_timeframe:
            raise ValueError("indicator candles must use one timeframe")
        if candle.open_time <= previous_open_time:
            raise ValueError("indicator candles must be ordered by open_time")
        if candle.is_closed is not True:
            raise ValueError("indicator candles must be closed")
        if not quality_allows_signal_use(candle.quality_flag):
            raise ValueError("indicator candle quality cannot drive indicator signal use")
        previous_open_time = candle.open_time


def _combined_quality_flag(candles: list[MarketCandle]) -> bool | str:
    if any(item.quality_flag == "degraded" for item in candles):
        return "degraded"
    return True


def _base_result(
    snapshot: IndicatorSnapshot,
    name: str,
    value: dict,
    signal: str,
    trend: str,
    strength: float,
    quality_flag: bool | str,
) -> IndicatorResult:
    return IndicatorResult(
        name=name,
        symbol=snapshot.symbol,
        timeframe=snapshot.timeframe,
        value=value,
        signal=signal,
        trend=trend,
        strength=max(0.0, min(float(strength), 1.0)),
        timestamp=snapshot.close_time,
        metadata=dict(value),
        quality_flag=quality_flag,
    )


def _build_macd_result(snapshot: IndicatorSnapshot, closes: list[float], quality_flag: bool | str) -> IndicatorResult:
    previous = macd(closes[:-1]) if len(closes) > 1 else None
    histogram = snapshot.macd_hist if snapshot.macd_hist is not None else 0.0
    previous_histogram = previous[2] if previous else histogram
    slope = histogram - previous_histogram
    if snapshot.macd is not None and snapshot.macd_signal is not None and snapshot.macd > snapshot.macd_signal:
        cross_state = "golden_cross"
    elif snapshot.macd is not None and snapshot.macd_signal is not None and snapshot.macd < snapshot.macd_signal:
        cross_state = "death_cross"
    else:
        cross_state = "neutral"
    trend = "UP" if histogram > 0 else "DOWN" if histogram < 0 else "NEUTRAL"
    signal = "BULLISH" if histogram > 0 and slope >= 0 else "BEARISH" if histogram < 0 and slope <= 0 else "NEUTRAL"
    value = {
        "macd_line": snapshot.macd,
        "signal_line": snapshot.macd_signal,
        "histogram": snapshot.macd_hist,
        "histogram_slope": slope,
        "cross_state": cross_state,
    }
    return _base_result(snapshot, "MACD", value, signal, trend, min(abs(histogram), 1.0), quality_flag)


def _build_cci_result(snapshot: IndicatorSnapshot, candles: list[Candle], quality_flag: bool | str) -> IndicatorResult:
    previous = cci(candles[:-1]) if len(candles) > 1 else None
    current = snapshot.cci if snapshot.cci is not None else 0.0
    slope = current - (previous if previous is not None else current)
    extreme = abs(current) > 150
    recovery = previous is not None and abs(previous) > 100 and abs(current) <= 100
    trend = "UP" if current > 100 else "DOWN" if current < -100 else "NEUTRAL"
    signal = "STRONG" if current > 100 else "WEAK" if current < -100 else "NEUTRAL"
    value = {"cci": snapshot.cci, "cci_slope": slope, "extreme_flag": extreme, "recovery_flag": recovery}
    return _base_result(snapshot, "CCI", value, signal, trend, min(abs(current) / 200, 1.0), quality_flag)


def _build_boll_result(snapshot: IndicatorSnapshot, closes: list[float], quality_flag: bool | str) -> IndicatorResult:
    previous = bollinger(closes[:-1]) if len(closes) > 1 else None
    width = 0.0
    previous_width = 0.0
    if snapshot.boll_upper is not None and snapshot.boll_lower is not None and snapshot.boll_mid:
        width = (snapshot.boll_upper - snapshot.boll_lower) / snapshot.boll_mid
    if previous and previous[0]:
        previous_width = (previous[1] - previous[2]) / previous[0]
    expansion = width > previous_width
    contraction = width < previous_width
    close = closes[-1]
    if snapshot.boll_upper is not None and close >= snapshot.boll_upper:
        position = "above_upper"
    elif snapshot.boll_lower is not None and close <= snapshot.boll_lower:
        position = "below_lower"
    elif snapshot.boll_mid is not None and close >= snapshot.boll_mid:
        position = "above_middle"
    else:
        position = "below_middle"
    trend = "UP" if position in {"above_upper", "above_middle"} else "DOWN"
    signal = "EXPANSION" if expansion else "CONTRACTION" if contraction else "NEUTRAL"
    value = {
        "middle_band": snapshot.boll_mid,
        "upper_band": snapshot.boll_upper,
        "lower_band": snapshot.boll_lower,
        "band_width": width,
        "band_expansion_flag": expansion,
        "band_contraction_flag": contraction,
        "price_position": position,
    }
    return _base_result(snapshot, "BOLL", value, signal, trend, min(width, 1.0), quality_flag)


def _build_rsi_result(snapshot: IndicatorSnapshot, closes: list[float], quality_flag: bool | str) -> IndicatorResult:
    previous = rsi(closes[:-1]) if len(closes) > 1 else None
    current = snapshot.rsi if snapshot.rsi is not None else 50.0
    slope = current - (previous if previous is not None else current)
    overbought = current > 70
    oversold = current < 30
    midline_state = "above_midline" if current > 55 else "below_midline" if current < 45 else "near_midline"
    trend = "UP" if current > 55 else "DOWN" if current < 45 else "NEUTRAL"
    signal = "OVERBOUGHT" if overbought else "OVERSOLD" if oversold else "NEUTRAL"
    value = {
        "rsi": snapshot.rsi,
        "rsi_slope": slope,
        "overbought_flag": overbought,
        "oversold_flag": oversold,
        "midline_state": midline_state,
    }
    return _base_result(snapshot, "RSI", value, signal, trend, abs(current - 50) / 50, quality_flag)


def _build_ema_result(snapshot: IndicatorSnapshot, closes: list[float], quality_flag: bool | str) -> IndicatorResult:
    close = closes[-1]
    ema_200 = snapshot.ema_200
    ema_9 = snapshot.ema_9
    ema_21 = snapshot.ema_21
    if ema_200 is not None and close > ema_200:
        gate_state = "long_allowed"
    elif ema_200 is not None and close < ema_200:
        gate_state = "short_allowed"
    else:
        gate_state = "neutral"
    if ema_9 is not None and ema_21 is not None and ema_9 > ema_21:
        momentum_state = "bullish"
    elif ema_9 is not None and ema_21 is not None and ema_9 < ema_21:
        momentum_state = "bearish"
    else:
        momentum_state = "neutral"
    slope = snapshot.ema50_slope or 0.0
    if gate_state == "long_allowed" and slope >= 0:
        trend = "UP"
    elif gate_state == "short_allowed" and slope <= 0:
        trend = "DOWN"
    else:
        trend = "NEUTRAL"
    if trend == "UP" and momentum_state == "bullish":
        signal = "BULLISH"
    elif trend == "DOWN" and momentum_state == "bearish":
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"
    value = {
        "ema_9": snapshot.ema_9,
        "ema_21": snapshot.ema_21,
        "ema_50": snapshot.ema_50,
        "ema_200": snapshot.ema_200,
        "ema50_slope": snapshot.ema50_slope,
        "ema9_21_gap": snapshot.ema9_21_gap,
        "bars_since_ema50_cross": snapshot.bars_since_ema50_cross,
        "bars_since_ema200_cross": snapshot.bars_since_ema200_cross,
        "gate_state": gate_state,
        "momentum_state": momentum_state,
    }
    return _base_result(snapshot, "EMA", value, signal, trend, min(abs(slope) * 100, 1.0), quality_flag)


def _build_cvd_result(snapshot: IndicatorSnapshot, candles: list[Candle], quality_flag: bool | str) -> IndicatorResult:
    cvd_values = cumulative_cvd(candles)
    previous_cvd = cvd_values[-2] if len(cvd_values) > 1 else cvd_values[-1]
    current_cvd = cvd_values[-1]
    slope = current_cvd - previous_cvd
    price_delta = candles[-1].close - candles[-2].close if len(candles) > 1 else 0.0
    divergence = (price_delta > 0 and slope < 0) or (price_delta < 0 and slope > 0)
    buy_pressure = max(snapshot.cvd_delta or 0.0, 0.0)
    sell_pressure = abs(min(snapshot.cvd_delta or 0.0, 0.0))
    trend = "UP" if slope > 0 else "DOWN" if slope < 0 else "NEUTRAL"
    signal = "DIVERGENCE" if divergence else "BUY_PRESSURE" if slope > 0 else "SELL_PRESSURE" if slope < 0 else "NEUTRAL"
    value = {
        "cvd": snapshot.cvd,
        "cvd_delta": snapshot.cvd_delta,
        "cvd_slope": slope,
        "cvd_divergence_flag": divergence,
        "buy_pressure": buy_pressure,
        "sell_pressure": sell_pressure,
    }
    return _base_result(snapshot, "CVD", value, signal, trend, min(abs(slope) / 100, 1.0), quality_flag)


def _build_atr_result(snapshot: IndicatorSnapshot, candles: list[Candle], quality_flag: bool | str) -> IndicatorResult:
    current_atr = snapshot.atr if snapshot.atr is not None else 0.0
    close = candles[-1].close
    atr_pct = current_atr / close if close else 0.0
    if atr_pct >= 0.05:
        volatility_state = "high"
    elif atr_pct <= 0.01:
        volatility_state = "low"
    else:
        volatility_state = "normal"
    value = {"atr": snapshot.atr, "atr_pct": atr_pct, "volatility_state": volatility_state}
    return _base_result(snapshot, "ATR", value, "RISK_ONLY", "NEUTRAL", min(atr_pct * 10, 1.0), quality_flag)
