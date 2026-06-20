from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean, pstdev
from typing import Mapping, Sequence

from src.backtest.engine import BacktestBar
from src.indicators.ema import bars_since_cross, ema, normalized_ema_slope
from src.signals.ema_scorer import EmaContext, ema_direction_gate, score_ema50_quality, score_ema_momentum


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
    return scores


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
