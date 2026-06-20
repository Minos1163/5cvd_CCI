from src.core.models import Candle
from src.data.data_contract import MarketCandle, validate_indicator_result
from src.indicators.cvd import cumulative_cvd
from src.indicators.indicator_engine import compute_indicator_results, compute_indicator_snapshot


def make_candles(count: int) -> list[Candle]:
    candles = []
    for i in range(count):
        close = 100 + i
        candles.append(
            Candle(
                symbol="BTCUSDT",
                timeframe="15m",
                open_time=i * 900,
                close_time=(i + 1) * 900,
                open=close - 0.5,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=100,
                taker_buy_volume=60,
            )
        )
    return candles


def test_cumulative_cvd_uses_taker_buy_minus_sell():
    candles = make_candles(3)
    assert cumulative_cvd(candles) == [20.0, 40.0, 60.0]


def test_compute_indicator_snapshot_populates_fields():
    snapshot = compute_indicator_snapshot(make_candles(220))
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.timeframe == "15m"
    assert snapshot.macd is not None
    assert snapshot.ema_9 is not None
    assert snapshot.ema_21 is not None
    assert snapshot.ema_50 is not None
    assert snapshot.ema_200 is not None
    assert snapshot.ema50_slope is not None
    assert snapshot.ema9_21_gap is not None
    assert snapshot.cci is not None
    assert snapshot.boll_mid is not None
    assert snapshot.atr is not None
    assert snapshot.cvd == 4400.0
    assert snapshot.cvd_delta == 20.0


def make_market_candles(count: int, *, is_closed: bool = True, quality_flag=True) -> list[MarketCandle]:
    candles = []
    for i in range(count):
        close = 100 + i
        candles.append(
            MarketCandle(
                symbol="BTCUSDT",
                timeframe="15m",
                open_time=i * 900,
                close_time=(i + 1) * 900,
                open=close - 0.5,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=100,
                quote_volume=10_000,
                trade_count=100,
                taker_buy_base_volume=60,
                taker_buy_quote_volume=6_000,
                is_closed=is_closed,
                source="unit_test",
                quality_flag=quality_flag,
            )
        )
    return candles


def test_compute_indicator_results_returns_standard_contracts():
    results = compute_indicator_results(make_market_candles(220))
    by_name = {item.name: item for item in results}

    assert set(by_name) == {"MACD", "CCI", "BOLL", "EMA", "CVD", "ATR"}
    assert set(by_name["MACD"].value) >= {"macd_line", "signal_line", "histogram", "histogram_slope", "cross_state"}
    assert set(by_name["EMA"].value) >= {
        "ema_9",
        "ema_21",
        "ema_50",
        "ema_200",
        "ema50_slope",
        "ema9_21_gap",
        "bars_since_ema50_cross",
        "bars_since_ema200_cross",
    }
    assert set(by_name["BOLL"].value) >= {
        "middle_band",
        "upper_band",
        "lower_band",
        "band_width",
        "band_expansion_flag",
        "band_contraction_flag",
        "price_position",
    }
    assert set(by_name["CVD"].value) >= {
        "cvd",
        "cvd_delta",
        "cvd_slope",
        "cvd_divergence_flag",
        "buy_pressure",
        "sell_pressure",
    }
    for result in results:
        assert validate_indicator_result(result).passed is True
        assert result.symbol == "BTCUSDT"
        assert result.timeframe == "15m"
        assert result.timestamp == 220 * 900


def test_compute_indicator_results_rejects_unclosed_market_candles():
    try:
        compute_indicator_results(make_market_candles(40, is_closed=False))
    except ValueError as exc:
        assert "closed" in str(exc)
    else:
        raise AssertionError("unfinished candles must be rejected")


def test_compute_indicator_results_marks_degraded_when_source_quality_degraded():
    results = compute_indicator_results(make_market_candles(40, quality_flag="degraded"))
    assert {item.quality_flag for item in results} == {"degraded"}


def test_compute_indicator_results_rejects_stale_quality():
    try:
        compute_indicator_results(make_market_candles(40, quality_flag="stale"))
    except ValueError as exc:
        assert "quality" in str(exc)
    else:
        raise AssertionError("stale candles must be rejected")
