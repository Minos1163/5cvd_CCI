from src.core.models import Candle
from src.indicators.cvd import cumulative_cvd
from src.indicators.indicator_engine import compute_indicator_snapshot


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
    snapshot = compute_indicator_snapshot(make_candles(40))
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.timeframe == "15m"
    assert snapshot.macd is not None
    assert snapshot.rsi is not None
    assert snapshot.cci is not None
    assert snapshot.boll_mid is not None
    assert snapshot.atr is not None
    assert snapshot.cvd == 800.0
    assert snapshot.cvd_delta == 20.0
