# -*- coding: utf-8 -*-
"""T1:BacktestBar 贯通 taker_buy_volume(五因子 F5 的数据入口)。

背景:评分层全程使用 BacktestBar,而 taker_buy_volume 原先只存在于
Candle / market_data_loader 路径,导致 F5「真实订单流」拿不到主动买量。
本测试锁定字段贯通行为与向后兼容性。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.engine import BacktestBar, _normalize_bar  # noqa: E402
from src.core.models import Candle  # noqa: E402


def _candle(**overrides) -> Candle:
    base = dict(
        symbol="BTCUSDT",
        timeframe="15m",
        open_time=0,
        close_time=1,
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        volume=100.0,
    )
    base.update(overrides)
    return Candle(**base)


def test_backtest_bar_defaults_taker_buy_volume_to_zero():
    bar = BacktestBar(
        symbol="BTCUSDT", timestamp=0, open=1.0, high=2.0, low=0.5, close=1.5, volume=100.0
    )
    assert bar.taker_buy_volume == 0.0


def test_normalize_from_candle_preserves_taker_buy_volume():
    bar = _normalize_bar(_candle(taker_buy_volume=62.5))
    assert bar.taker_buy_volume == 62.5


def test_normalize_from_mapping_preserves_taker_buy_volume():
    bar = _normalize_bar(
        {
            "symbol": "ETHUSDT",
            "timestamp": 5,
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "volume": 10.0,
            "taker_buy_volume": 4.0,
        }
    )
    assert bar.taker_buy_volume == 4.0


def test_normalize_from_mapping_missing_field_defaults_zero():
    bar = _normalize_bar(
        {
            "symbol": "ETHUSDT",
            "timestamp": 5,
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "volume": 10.0,
        }
    )
    assert bar.taker_buy_volume == 0.0


def test_normalize_passthrough_backtest_bar_keeps_value():
    original = BacktestBar(
        symbol="BTCUSDT",
        timestamp=0,
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        volume=100.0,
        taker_buy_volume=33.0,
    )
    assert _normalize_bar(original) is original
