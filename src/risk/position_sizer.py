from __future__ import annotations

from dataclasses import dataclass


NO_TRADE = "NO_TRADE"
ENTRY_MODE_MULTIPLIERS = {"DIRECT": 1.0, "PROBE": 0.25}
SIGNAL_MULTIPLIERS = ENTRY_MODE_MULTIPLIERS
MARKET_TIER_MULTIPLIERS = {"A": 2.0, "B": 1.0, "C": 0.75}
VOLATILITY_FACTORS = {"NORMAL": 1.0, "HIGH": 0.5, "EXTREME": 0.0}
POSITION_REQUIRED_INPUTS = [
    "account_equity",
    "available_margin",
    "symbol_price",
    "leverage",
    "stop_pct",
    "risk_per_trade_pct",
    "symbol_tier",
    "open_exposure",
    "portfolio_exposure",
    "correlation_group",
    "position_side",
    "entry_mode",
    "volatility_state",
]
POSITION_DECISION_STEPS = [
    "read_account_equity_and_available_margin",
    "read_entry_mode",
    "read_stop_pct",
    "calculate_standard_notional",
    "apply_symbol_tier_factor",
    "apply_portfolio_exposure_limit",
    "apply_account_risk_factor",
    "check_min_notional",
    "check_min_margin",
    "output_final_executable_size",
]
POSITION_LOG_FIELDS = [
    "symbol",
    "entry_mode",
    "account_equity",
    "available_margin",
    "risk_amount",
    "stop_pct",
    "standard_notional",
    "probe_notional",
    "direct_notional",
    "tier_factor",
    "account_risk_factor",
    "portfolio_risk_factor",
    "final_notional",
    "final_qty",
    "min_notional_check",
    "leverage",
    "decision",
]
STATE_POSITION_POLICY = {
    "WATCH": "prepare_only",
    "PROBE": "probe_size",
    "DIRECT": "direct_size",
    "MANAGE": "manage_only",
    "EXIT": "close_only",
}


@dataclass(frozen=True)
class PositionSizingInput:
    symbol: str
    signal_type: str
    equity: float
    available_margin: float
    price: float
    leverage: float
    stop_pct: float
    atr: float
    risk_pct: float
    market_tier: str
    current_open_exposure: float
    portfolio_correlation: float
    min_notional: float
    max_total_exposure_pct: float
    entry_mode: str | None = None
    risk_per_trade_pct: float | None = None
    symbol_tier: str | None = None
    position_side: str = "BOTH"
    volatility_state: str = "NORMAL"
    account_risk_factor: float = 1.0
    portfolio_risk_factor: float = 1.0
    min_margin: float = 0.0
    max_leverage: float = 5.0
    symbol_exposure: float = 0.0
    max_symbol_exposure_pct: float = 0.20
    side_exposure: float = 0.0
    max_side_exposure_pct: float = 0.75
    correlation_group: str = ""
    correlation_group_exposure: float = 0.0
    max_correlation_group_exposure_pct: float = 0.50
    open_positions_count: int = 0
    max_open_positions: int = 5
    quantity_step: float = 0.0
    data_quality_ok: bool = True
    state_allows_entry: bool = True
    cooldown_active: bool = False
    leverage_set: bool = True


@dataclass(frozen=True)
class PositionSizingResult:
    approved: bool
    reason: str
    symbol: str
    signal_type: str
    standard_notional: float
    notional: float
    quantity: float
    required_margin: float
    risk_amount: float
    signal_multiplier: float
    market_tier: str
    market_tier_multiplier: float
    decision: str = NO_TRADE
    entry_mode: str = NO_TRADE
    final_notional: float = 0.0
    final_qty: float = 0.0
    tier_factor: float = 1.0
    account_risk_factor: float = 1.0
    portfolio_risk_factor: float = 1.0
    volatility_factor: float = 1.0
    min_notional_check: bool = False
    min_margin_check: bool = False
    leverage_value: float = 0.0
    position_side: str = "BOTH"
    correlation_group: str = ""
    audit: dict | None = None


def size_notional(equity: float, risk_pct: float, stop_pct: float, signal_type: str) -> float:
    if equity <= 0:
        raise ValueError("equity must be positive")
    if risk_pct <= 0:
        raise ValueError("risk_pct must be positive")
    if stop_pct <= 0:
        raise ValueError("stop_pct must be positive")
    base = equity * risk_pct / stop_pct
    if signal_type.upper() == "PROBE":
        return base * 0.25
    return base


def reject_if_below_min_notional(notional: float, min_notional: float) -> tuple[bool, str]:
    if notional < min_notional:
        return False, "notional below exchange minimum; skip instead of inflating size"
    return True, "approved"


def signal_multiplier(signal_type: str) -> float:
    value = signal_type.strip().upper()
    if value not in ENTRY_MODE_MULTIPLIERS:
        raise ValueError("signal_type must be DIRECT or PROBE")
    return ENTRY_MODE_MULTIPLIERS[value]


def market_tier_multiplier(market_tier: str) -> float:
    value = market_tier.strip().upper()
    if value not in MARKET_TIER_MULTIPLIERS:
        raise ValueError("market_tier must be A, B, or C")
    return MARKET_TIER_MULTIPLIERS[value]


def normalize_entry_mode(request: PositionSizingInput) -> str:
    value = request.entry_mode if request.entry_mode is not None else request.signal_type
    normalized = value.strip().upper()
    if normalized in {"NO_TRADE", "NONE", "WAIT"}:
        return NO_TRADE
    if normalized not in ENTRY_MODE_MULTIPLIERS:
        raise ValueError("entry_mode must be DIRECT, PROBE, or NO_TRADE")
    return normalized


def normalized_symbol_tier(request: PositionSizingInput) -> str:
    value = request.symbol_tier if request.symbol_tier is not None else request.market_tier
    return value.strip().upper()


def effective_risk_pct(request: PositionSizingInput) -> float:
    return request.risk_per_trade_pct if request.risk_per_trade_pct is not None else request.risk_pct


def volatility_factor(volatility_state: str) -> float:
    value = volatility_state.strip().upper()
    if value not in VOLATILITY_FACTORS:
        raise ValueError("volatility_state must be NORMAL, HIGH, or EXTREME")
    return VOLATILITY_FACTORS[value]


def floor_quantity(quantity: float, quantity_step: float) -> float:
    if quantity_step <= 0:
        return quantity
    steps = int(quantity / quantity_step)
    return steps * quantity_step


def calculate_position_size(request: PositionSizingInput) -> PositionSizingResult:
    _validate_request(request)
    entry_mode = normalize_entry_mode(request)
    normalized_tier = normalized_symbol_tier(request)
    sig_multiplier = ENTRY_MODE_MULTIPLIERS.get(entry_mode, 0.0)
    tier_multiplier = market_tier_multiplier(normalized_tier)
    vol_factor = volatility_factor(request.volatility_state)
    risk_pct = effective_risk_pct(request)
    risk_amount = request.equity * risk_pct
    standard_notional = risk_amount / request.stop_pct
    probe_notional = standard_notional * ENTRY_MODE_MULTIPLIERS["PROBE"]
    direct_notional = standard_notional * ENTRY_MODE_MULTIPLIERS["DIRECT"]
    raw_notional = (
        standard_notional
        * sig_multiplier
        * tier_multiplier
        * request.account_risk_factor
        * request.portfolio_risk_factor
        * vol_factor
    )
    raw_quantity = raw_notional / request.price
    quantity = floor_quantity(raw_quantity, request.quantity_step)
    notional = quantity * request.price
    required_margin = notional / request.leverage

    gate_reason = _gate_no_trade(request, entry_mode)
    if gate_reason is not None:
        return _result(
            request,
            False,
            gate_reason,
            standard_notional,
            0.0,
            0.0,
            0.0,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            False,
            False,
        )

    if vol_factor == 0:
        return _result(
            request,
            False,
            "volatility state blocks new position",
            standard_notional,
            0.0,
            0.0,
            0.0,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            False,
            False,
        )

    raw_ok, reason = reject_if_below_min_notional(raw_notional, request.min_notional)
    if not raw_ok:
        return _result(
            request,
            False,
            reason,
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            False,
            required_margin >= request.min_margin,
        )

    ok, reason = reject_if_below_min_notional(notional, request.min_notional)
    if not ok:
        return _result(
            request,
            False,
            "notional below exchange minimum after precision floor; skip instead of inflating size",
            standard_notional,
            notional,
            quantity,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            False,
            required_margin >= request.min_margin,
        )
    if required_margin > request.available_margin:
        return _result(
            request,
            False,
            "required margin exceeds available margin",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            required_margin >= request.min_margin,
        )
    if required_margin < request.min_margin:
        return _result(
            request,
            False,
            "required margin below exchange minimum",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            False,
        )
    if (request.current_open_exposure + notional) / request.equity > request.max_total_exposure_pct:
        return _result(
            request,
            False,
            "total exposure limit exceeded",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            True,
        )
    if (request.symbol_exposure + notional) / request.equity > request.max_symbol_exposure_pct:
        return _result(
            request,
            False,
            "symbol exposure limit exceeded",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            True,
        )
    if (request.side_exposure + notional) / request.equity > request.max_side_exposure_pct:
        return _result(
            request,
            False,
            "side exposure limit exceeded",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            True,
        )
    if (
        request.correlation_group_exposure + notional
    ) / request.equity > request.max_correlation_group_exposure_pct:
        return _result(
            request,
            False,
            "correlation group exposure limit exceeded",
            standard_notional,
            notional,
            0.0,
            required_margin,
            risk_amount,
            sig_multiplier,
            tier_multiplier,
            entry_mode,
            NO_TRADE,
            vol_factor,
            probe_notional,
            direct_notional,
            True,
            True,
        )

    return _result(
        request,
        True,
        "approved",
        standard_notional,
        notional,
        quantity,
        required_margin,
        risk_amount,
        sig_multiplier,
        tier_multiplier,
        entry_mode,
        entry_mode,
        vol_factor,
        probe_notional,
        direct_notional,
        True,
        True,
    )


def _validate_request(request: PositionSizingInput) -> None:
    positive_fields = {
        "equity": request.equity,
        "price": request.price,
        "leverage": request.leverage,
        "stop_pct": request.stop_pct,
        "atr": request.atr,
        "risk_pct": request.risk_pct,
        "min_notional": request.min_notional,
        "max_total_exposure_pct": request.max_total_exposure_pct,
        "account_risk_factor": request.account_risk_factor,
        "portfolio_risk_factor": request.portfolio_risk_factor,
        "max_leverage": request.max_leverage,
        "max_symbol_exposure_pct": request.max_symbol_exposure_pct,
        "max_side_exposure_pct": request.max_side_exposure_pct,
        "max_correlation_group_exposure_pct": request.max_correlation_group_exposure_pct,
        "max_open_positions": request.max_open_positions,
    }
    if request.risk_per_trade_pct is not None:
        positive_fields["risk_per_trade_pct"] = request.risk_per_trade_pct
    for name, value in positive_fields.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    if request.available_margin < 0:
        raise ValueError("available_margin must be non-negative")
    if request.current_open_exposure < 0:
        raise ValueError("current_open_exposure must be non-negative")
    if request.portfolio_correlation < 0:
        raise ValueError("portfolio_correlation must be non-negative")
    if request.min_margin < 0:
        raise ValueError("min_margin must be non-negative")
    if request.symbol_exposure < 0:
        raise ValueError("symbol_exposure must be non-negative")
    if request.side_exposure < 0:
        raise ValueError("side_exposure must be non-negative")
    if request.correlation_group_exposure < 0:
        raise ValueError("correlation_group_exposure must be non-negative")
    if request.open_positions_count < 0:
        raise ValueError("open_positions_count must be non-negative")
    if request.quantity_step < 0:
        raise ValueError("quantity_step must be non-negative")


def _gate_no_trade(request: PositionSizingInput, entry_mode: str) -> str | None:
    if entry_mode == NO_TRADE:
        return "entry mode is NO_TRADE"
    if not request.data_quality_ok:
        return "data quality is not tradable"
    if not request.state_allows_entry:
        return "state machine does not allow new position"
    if request.cooldown_active:
        return "cooldown is active"
    if not request.leverage_set:
        return "leverage must be set before sizing"
    if request.leverage > request.max_leverage:
        return "leverage exceeds system maximum"
    if request.open_positions_count >= request.max_open_positions:
        return "max simultaneous positions reached"
    return None


def _result(
    request: PositionSizingInput,
    approved: bool,
    reason: str,
    standard_notional: float,
    notional: float,
    quantity: float,
    required_margin: float,
    risk_amount: float,
    sig_multiplier: float,
    tier_multiplier: float,
    entry_mode: str,
    decision: str,
    vol_factor: float,
    probe_notional: float,
    direct_notional: float,
    min_notional_check: bool,
    min_margin_check: bool,
) -> PositionSizingResult:
    min_notional_check = min_notional_check and notional >= request.min_notional
    audit = {
        "symbol": request.symbol.strip().upper(),
        "entry_mode": entry_mode,
        "account_equity": request.equity,
        "available_margin": request.available_margin,
        "risk_amount": risk_amount,
        "stop_pct": request.stop_pct,
        "standard_notional": standard_notional,
        "probe_notional": probe_notional,
        "direct_notional": direct_notional,
        "tier_factor": tier_multiplier,
        "account_risk_factor": request.account_risk_factor,
        "portfolio_risk_factor": request.portfolio_risk_factor,
        "final_notional": notional,
        "final_qty": quantity,
        "min_notional_check": min_notional_check,
        "leverage": request.leverage,
        "decision": decision,
    }
    return PositionSizingResult(
        approved=approved,
        reason=reason,
        symbol=request.symbol.strip().upper(),
        signal_type=entry_mode,
        standard_notional=standard_notional,
        notional=notional,
        quantity=quantity,
        required_margin=required_margin,
        risk_amount=risk_amount,
        signal_multiplier=sig_multiplier,
        market_tier=normalized_symbol_tier(request),
        market_tier_multiplier=tier_multiplier,
        decision=decision,
        entry_mode=entry_mode,
        final_notional=notional,
        final_qty=quantity,
        tier_factor=tier_multiplier,
        account_risk_factor=request.account_risk_factor,
        portfolio_risk_factor=request.portfolio_risk_factor,
        volatility_factor=vol_factor,
        min_notional_check=min_notional_check,
        min_margin_check=min_margin_check,
        leverage_value=request.leverage,
        position_side=request.position_side.strip().upper(),
        correlation_group=request.correlation_group,
        audit=audit,
    )
