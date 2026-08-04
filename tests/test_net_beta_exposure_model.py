from __future__ import annotations

from dataclasses import dataclass

from src.risk.net_beta_exposure_model import (
    NET_BETA_EXPOSURE_CAP_PCT,
    compute_net_beta_exposure,
    net_beta_exposure_within_limit,
)


@dataclass
class Position:
    symbol: str
    side: str
    notional: float
    remaining_fraction: float


def test_compute_net_beta_exposure_sums_signed_remaining_notional() -> None:
    positions = {
        "BTCUSDT": {"symbol": "BTCUSDT", "side": "LONG", "notional": 1000.0, "remaining_fraction": 1.0},
        "HYPEUSDT": {"symbol": "HYPEUSDT", "side": "SHORT", "notional": 500.0, "remaining_fraction": 0.5},
    }

    assert compute_net_beta_exposure(positions, equity=10_000.0) == 0.055


def test_compute_net_beta_exposure_accepts_position_objects() -> None:
    positions = {
        "CCUSDT": Position("CCUSDT", "LONG", 1000.0, 0.5),
        "XMRUSDT": Position("XMRUSDT", "SHORT", 1000.0, 1.0),
    }

    assert compute_net_beta_exposure(positions, equity=10_000.0) == 0.015


def test_net_beta_exposure_limit_uses_absolute_value() -> None:
    assert net_beta_exposure_within_limit(-NET_BETA_EXPOSURE_CAP_PCT, NET_BETA_EXPOSURE_CAP_PCT)
    assert not net_beta_exposure_within_limit(-0.51, NET_BETA_EXPOSURE_CAP_PCT)
