from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean, pstdev
from typing import Mapping, Sequence

from src.backtest.engine import BacktestBar
from src.indicators.ema import bars_since_cross, ema, normalized_ema_slope
from src.signals.cci_quality import cci_series, score_cci_momentum_quality
from src.signals.ema_scorer import EmaContext, ema_direction_gate, score_ema50_quality, score_ema_momentum
from src.signals.fib_location import compute_fib_levels, detect_fractal_swings, score_fibonacci_location
from src.signals.pa_structure import score_price_action_structure


TP1_R_MULTIPLIER = 1.2


def completed_bars(bars: Sequence[BacktestBar], timestamp: int) -> list[BacktestBar]:
    return [bar for bar in bars if bar.timestamp <= timestamp]


def direction_from_history(bars: Sequence[BacktestBar]) -> str:
    if len(bars) < 4:
        return "NONE"
    recent = bars[-1].close
    prior = bars[-4].close
    change = (recent - prior) / prior if prior > 0 else 0.0
    if change > 0.003:
        return "LONG"
    if change < -0.003:
        return "SHORT"
    return "NONE"


def component_scores(
    side: str,
    completed: Mapping[str, Sequence[BacktestBar]],
    atr_pct_value: float,
    *,
    use_ema_architecture: bool = False,
    ema200_gate_mode: str = "hard",
    use_fib_pa_architecture: bool = False,
) -> dict[str, float]:
    scores = {
        "background_4h": agreement_score(side, completed.get("4h", []), 3),
        "direction_1h": agreement_score(side, completed.get("1h", []), 4),
        "quality_30m": agreement_score(side, completed.get("30m", []), 6),
        "trigger_15m": trigger_score(side, completed.get("15m", [])),
        "cvd_flow": volume_flow_score(side, completed.get("15m", [])),
        "volatility_stop": 1.0 if 0.005 <= atr_pct_value <= 0.04 else 0.2,
        "liquidity_execution": 1.0,
        "market_regime": 0.8,
    }
    if use_ema_architecture:
        ema_context = ema_context_from_bars(completed.get("15m", []))
        if ema_context is None:
            scores["ema_200_gate"] = 0.0
            scores["ema_50_quality"] = 0.0
            scores["ema_momentum"] = 0.0
        else:
            gate = ema_direction_gate(side, ema_context, mode=ema200_gate_mode)
            scores["ema_200_gate"] = 1.0 if gate.allowed else 0.0
            if gate.allowed:
                scores["ema_50_quality"] = max(0.0, score_ema50_quality(side, ema_context) + gate.penalty)
                scores["ema_momentum"] = score_ema_momentum(side, ema_context)
            else:
                scores["ema_50_quality"] = 0.0
                scores["ema_momentum"] = 0.0
    if use_fib_pa_architecture:
        scores.update(fib_pa_component_scores(side, completed, atr_pct_value, ema200_gate_mode=ema200_gate_mode))
    return scores


def fib_pa_component_scores(
    side: str,
    completed: Mapping[str, Sequence[BacktestBar]],
    atr_pct_value: float,
    *,
    ema200_gate_mode: str = "soft",
) -> dict[str, float]:
    bars_15m = list(completed.get("15m", []))
    bars_1h = list(completed.get("1h", []))
    latest_close = bars_15m[-1].close if bars_15m else 0.0
    atr_value = latest_close * max(0.0, atr_pct_value)

    ema_score = trend_ema_context_score(side, bars_15m, ema200_gate_mode)
    cvd_score = volume_flow_score(side, bars_15m)
    cci_result = score_cci_momentum_quality(cci_series(bars_15m), side)

    swings_15m = detect_fractal_swings(bars_15m, atr=atr_value)
    pa_result = score_price_action_structure(bars_15m, side, swings_15m, atr=atr_value)

    fib_1h = latest_fib_from_bars(bars_1h, side, atr_value)
    fib_15m = latest_fib_from_bars(bars_15m, side, atr_value)
    fib_result = score_fibonacci_location(
        close=latest_close,
        side=side,
        fib_1h=fib_1h,
        fib_15m=fib_15m,
        atr=atr_value,
    )

    rr_detail = risk_reward_geometry_detail(latest_close, side, atr_value, atr_pct_value, swings_15m)

    return {
        "trend_ema_context": ema_score,
        "flow_cvd_confirmation": cvd_score,
        "cci_momentum_quality": max(0.0, min(1.0, cci_result.score / 14.0)),
        "price_action_structure": max(0.0, min(1.0, pa_result.score / 22.0)),
        "fibonacci_location": max(0.0, min(1.0, fib_result.score / 18.0)),
        "risk_reward_geometry": max(0.0, min(1.0, float(rr_detail["score"]) / 8.0)),
        "fib_action_cap": 0.0 if fib_result.action_cap == "NO_TRADE" else 1.0,
    }


def trend_ema_context_score(side: str, bars: Sequence[BacktestBar], ema200_gate_mode: str) -> float:
    context = ema_context_from_bars(bars)
    if context is None:
        return 0.0
    gate = ema_direction_gate(side, context, mode=ema200_gate_mode)
    gate_score = 8.0 if gate.allowed else 0.0
    ema50_score = max(0.0, score_ema50_quality(side, context) + gate.penalty) * 7.0 if gate.allowed else 0.0
    momentum_score = score_ema_momentum(side, context) * 5.0 if gate.allowed else 0.0
    return max(0.0, min(1.0, (gate_score + ema50_score + momentum_score) / 20.0))


def latest_fib_from_bars(
    bars: Sequence[BacktestBar],
    side: str,
    atr_value: float,
) -> dict[str, float] | None:
    swings = detect_fractal_swings(bars, atr=atr_value)
    highs = [item.price for item in swings if item.kind == "HIGH"]
    lows = [item.price for item in swings if item.kind == "LOW"]
    if not highs or not lows:
        return None
    trend = "DOWN" if side.strip().upper() == "SHORT" else "UP"
    swing_high = max(highs[-3:])
    swing_low = min(lows[-3:])
    levels = compute_fib_levels(swing_high, swing_low, trend)
    return levels or None


def risk_reward_geometry_score(
    close: float,
    side: str,
    atr_value: float,
    atr_pct_value: float,
    swings: Sequence[object],
) -> float:
    return float(risk_reward_geometry_detail(close, side, atr_value, atr_pct_value, swings)["score"])


def risk_reward_geometry_detail(
    close: float,
    side: str,
    atr_value: float,
    atr_pct_value: float,
    swings: Sequence[object],
) -> dict[str, float | str | None]:
    if close <= 0 or atr_value <= 0:
        return {
            "score": 0.0,
            "net_tp1_r": 0.0,
            "stop_pct": 0.0,
            "tp1_pct": 0.0,
            "opposition_dist_r": None,
            "rr_zero_reason": "INVALID_INPUT",
        }
    stop_dist = max(close * 0.005, min(close * 0.030, atr_value * 1.5))
    tp1_dist = stop_dist * TP1_R_MULTIPLIER
    net_tp1_r = (tp1_dist - close * 0.001) / stop_dist if stop_dist > 0 else 0.0
    if net_tp1_r >= 1.3:
        score = 5.0
    elif net_tp1_r >= 1.1:
        score = 3.5
    elif net_tp1_r >= 0.9:
        score = 2.0
    else:
        score = 0.0

    opposition = nearest_opposition_price(close, side, swings)
    opposition_too_close = False
    opposition_dist_r = None
    if opposition is not None:
        if side.strip().upper() == "SHORT":
            distance = close - opposition
        else:
            distance = opposition - close
        opposition_dist_r = distance / stop_dist if stop_dist > 0 else None
        if 0 < distance < stop_dist * 0.7:
            score -= 3.0
            opposition_too_close = True
        elif 0 < distance < stop_dist:
            score -= 1.5

    atr_out_of_range = False
    if 0.008 <= atr_pct_value <= 0.025:
        score += 3.0
    elif 0.005 <= atr_pct_value < 0.008:
        score += 1.5
    elif atr_pct_value > 0.030:
        score += 1.0
    else:
        atr_out_of_range = True

    final_score = max(0.0, min(8.0, score))
    rr_zero_reason = ""
    if final_score <= 0.0:
        if net_tp1_r < 0.9:
            rr_zero_reason = "NET_TP1_R_TOO_LOW"
        elif opposition_too_close:
            rr_zero_reason = "OPPOSITION_STRUCTURE_TOO_CLOSE"
        elif atr_out_of_range:
            rr_zero_reason = "ATR_OUT_OF_RANGE"
        else:
            rr_zero_reason = "UNKNOWN"

    return {
        "score": round(final_score, 4),
        "net_tp1_r": round(net_tp1_r, 3),
        "stop_pct": round(stop_dist / close, 4),
        "tp1_pct": round(tp1_dist / close, 4),
        "opposition_dist_r": round(opposition_dist_r, 3) if opposition_dist_r is not None else None,
        "rr_zero_reason": rr_zero_reason,
    }


def nearest_opposition_price(close: float, side: str, swings: Sequence[object]) -> float | None:
    normalized = side.strip().upper()
    if normalized == "SHORT":
        supports = [float(item.price) for item in swings if getattr(item, "kind", "") == "LOW" and item.price < close]
        return max(supports) if supports else None
    resistances = [float(item.price) for item in swings if getattr(item, "kind", "") == "HIGH" and item.price > close]
    return min(resistances) if resistances else None


def ema_context_from_bars(bars: Sequence[BacktestBar]) -> EmaContext | None:
    if len(bars) < 200:
        return None
    closes = [bar.close for bar in bars]
    ema_9_series = ema(closes, 9)
    ema_21_series = ema(closes, 21)
    ema_50_series = ema(closes, 50)
    ema_200_series = ema(closes, 200)
    if not all((ema_9_series, ema_21_series, ema_50_series, ema_200_series)):
        return None
    ema_9 = ema_9_series[-1]
    ema_21 = ema_21_series[-1]
    ema9_21_gap = (ema_9 - ema_21) / ema_21 if ema_21 else 0.0
    return EmaContext(
        close=closes[-1],
        ema_9=ema_9,
        ema_21=ema_21,
        ema_50=ema_50_series[-1],
        ema_200=ema_200_series[-1],
        ema50_slope=normalized_ema_slope(ema_50_series, 5),
        ema9_21_gap=ema9_21_gap,
        bars_since_ema50_cross=bars_since_cross(closes[-len(ema_50_series) :], ema_50_series),
        bars_since_ema200_cross=bars_since_cross(closes[-len(ema_200_series) :], ema_200_series),
    )


def agreement_score(side: str, bars: Sequence[BacktestBar], lookback: int) -> float:
    if len(bars) <= lookback:
        return 0.0
    change = (bars[-1].close - bars[-lookback].close) / bars[-lookback].close
    if side == "LONG":
        return max(0.0, min(1.0, 0.5 + change * 50.0))
    return max(0.0, min(1.0, 0.5 - change * 50.0))


def trigger_score(side: str, bars: Sequence[BacktestBar]) -> float:
    if len(bars) < 3:
        return 0.0
    change = (bars[-1].close - bars[-2].close) / bars[-2].close
    if side == "LONG":
        return 1.0 if change > 0.0015 else 0.4 if change > 0 else 0.0
    return 1.0 if change < -0.0015 else 0.4 if change < 0 else 0.0


def volume_flow_score(side: str, bars: Sequence[BacktestBar]) -> float:
    if len(bars) < 6:
        return 0.0
    signed = 0.0
    for bar in bars[-6:]:
        direction = 1.0 if bar.close >= bar.open else -1.0
        signed += direction * bar.volume
    if signed == 0:
        return 0.5
    if side == "LONG":
        return 1.0 if signed > 0 else 0.2
    return 1.0 if signed < 0 else 0.2


def atr_pct(bars: Sequence[BacktestBar]) -> float:
    if len(bars) < 2:
        return 0.0
    true_ranges = []
    previous_close = bars[0].close
    for bar in bars[1:]:
        true_ranges.append(max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close)))
        previous_close = bar.close
    close = bars[-1].close
    return sum(true_ranges) / len(true_ranges) / close if close > 0 and true_ranges else 0.0


def quote_volume(bars: Sequence[BacktestBar]) -> float:
    return sum(bar.close * bar.volume for bar in bars)


def long_overextension_active(bars: Sequence[BacktestBar]) -> bool:
    if len(bars) < 20:
        return False
    closes = [bar.close for bar in bars[-20:]]
    average = mean(closes)
    deviation = pstdev(closes)
    upper_band = average + 2.0 * deviation
    return closes[-1] >= upper_band


def long_upper_wick_risk_active(bars: Sequence[BacktestBar]) -> bool:
    if not bars:
        return False
    bar = bars[-1]
    body = abs(bar.close - bar.open)
    upper_wick = bar.high - max(bar.open, bar.close)
    if upper_wick <= 0:
        return False
    return upper_wick >= max(body, 1e-12) * 2.0


def long_chase_risk_active(bars: Sequence[BacktestBar], atr_pct_value: float) -> bool:
    if len(bars) < 8 or atr_pct_value <= 0:
        return False
    start = bars[-8].close
    end = bars[-1].close
    if start <= 0:
        return False
    return (end - start) / start > atr_pct_value * 2.0


def extreme_position_ratio(bars: Sequence[BacktestBar], lookback: int = 8) -> float:
    """当前 close 在近 lookback 根 [low, high] 区间内的相对位置。

    0.0 = 贴近区间最低点, 1.0 = 贴近区间最高点。
    用于"非极值追单"检查(08-02 报告 Task A 量化定义: close 不在
    最近 8 根 K 线极值区间的最外 20%, 即 ratio 应落在 [0.20, 0.80])。
    样本不足或区间退化时返回 0.5(中性, 不阻断)。
    """
    window = list(bars)[-lookback:]
    if len(window) < 3:
        return 0.5
    lo = min(bar.low for bar in window)
    hi = max(bar.high for bar in window)
    if hi <= lo:
        return 0.5
    close = window[-1].close
    return (close - lo) / (hi - lo)


def long_low_liquidity_session_active(timestamp: int, bars: Sequence[BacktestBar]) -> bool:
    if len(bars) < 40:
        return False
    hour = datetime.fromtimestamp(timestamp, tz=UTC).hour
    if hour not in {22, 23, 0}:
        return False
    recent_volume = mean(bar.volume for bar in bars[-8:])
    prior_volume = mean(bar.volume for bar in bars[-40:-8])
    return prior_volume > 0 and recent_volume < prior_volume * 0.8


def wick_anomaly(current_bar: BacktestBar, previous_bar: BacktestBar) -> bool:
    if current_bar.low <= 0:
        return True
    high_low_ratio = current_bar.high / current_bar.low
    low_volume = current_bar.volume < previous_bar.volume * 0.5 if previous_bar.volume > 0 else False
    return high_low_ratio > 1.05 and low_volume
