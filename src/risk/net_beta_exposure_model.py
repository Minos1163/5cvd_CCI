from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping


STATIC_BTC_BETA: dict[str, float] = {
    "BTCUSDT": 1.00,
    "ETHUSDT": 1.05,
    "BNBUSDT": 0.90,
    "SOLUSDT": 1.25,
    "ADAUSDT": 1.20,
    "LINKUSDT": 1.15,
    "DOGEUSDT": 1.30,
    "XRPUSDT": 1.10,
    "TRXUSDT": 0.85,
    "BCHUSDT": 1.10,
    "XLMUSDT": 1.15,
    "XMRUSDT": 0.75,
    "ZECUSDT": 1.35,
    "TONUSDT": 1.05,
    "HYPEUSDT": 1.80,
    "LABUSDT": 1.80,
    "CCUSDT": 1.80,
}
DEFAULT_BTC_BETA = 1.20
NET_BETA_EXPOSURE_CAP_PCT = 0.50
NET_BETA_EXPOSURE_MODEL_NAME = "static_v1_observation_only"


def compute_net_beta_exposure(open_positions: Mapping[str, Any], equity: float = 10_000.0) -> float:
    if equity <= 0:
        return 0.0
    total = 0.0
    for raw_symbol, raw_position in open_positions.items():
        position = _position_mapping(raw_position)
        symbol = str(position.get("symbol") or raw_symbol).strip().upper()
        side = str(position.get("side") or "").strip().upper()
        if side not in {"LONG", "SHORT"}:
            continue
        notional = _float_value(position.get("notional"))
        remaining_fraction = max(0.0, _float_value(position.get("remaining_fraction"), default=1.0))
        signed = 1.0 if side == "LONG" else -1.0
        beta = STATIC_BTC_BETA.get(symbol, DEFAULT_BTC_BETA)
        total += signed * beta * notional * remaining_fraction / equity
    return round(total, 6)


def net_beta_exposure_within_limit(value: float, limit: float) -> bool:
    return abs(float(value)) <= abs(float(limit))


def _position_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return asdict(value)
    payload: dict[str, Any] = {}
    for field in ("symbol", "side", "notional", "remaining_fraction"):
        if hasattr(value, field):
            payload[field] = getattr(value, field)
    return payload


def _float_value(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
