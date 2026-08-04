from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from src.backtest.fee_model import fee


INITIAL_EQUITY = 10_000.0
FEE_BPS = 5.0
SLIPPAGE_BPS = 5.0
ATR_STOP_MULT = 1.5
MIN_STOP_PCT = 0.005
MAX_STOP_PCT = 0.03
MAX_HOLD_BARS = 32
COST_BREAKEVEN_CHECK_BARS = MAX_HOLD_BARS // 4
COST_BREAKEVEN_BUFFER_MULT = 0.5
TP_LEVELS = (1.2, 2.0, 3.0)
TP_FRACTIONS = (0.40, 0.35, 0.25)


@dataclass(frozen=True)
class PaperExitConfig:
    mode: str = "legacy"
    trend_trigger_r: float = 1.5
    trailing_r_mult: float = 1.0
    early_breakeven_enabled: bool = False
    early_breakeven_trigger_r: float = 1.0


@dataclass
class PaperPosition:
    symbol: str
    side: str
    entry_time: int
    entry_price: float
    quantity: float
    notional: float
    leverage: int
    stop_price: float
    tp_prices: list[float]
    tp_fractions: list[float]
    tp_consumed: list[int]
    remaining_fraction: float
    realized_pnl: float
    realized_margin_pnl: float
    entry_fee: float
    entry_slippage: float
    last_price: float
    best_price: float
    max_favorable_r_observed: float
    hold_bars: int
    last_processed_kline_ts: int
    score: float
    reasons: list[str]
    exit_mode: str = "legacy"
    scout_mission: str | None = None
    experiment_id: str | None = None
    entry_channel: str | None = None
    source_quadrant: str | None = None
    q3_reduced: bool = False
    q4_streak: int = 0


@dataclass(frozen=True)
class PortfolioStateSnapshot:
    active_symbols: set[str]
    open_position_count: int
    total_exposure_pct: float
    same_direction_long_pct: float
    same_direction_short_pct: float
    daily_trades_by_symbol: dict[str, int]
    portfolio_trades_today: int
    daily_profit_pct: float
    symbol_exposure_pct: dict[str, float]


class PaperTradingLedger:
    def __init__(
        self,
        output_dir: str | Path,
        *,
        state_dir: str | Path | None = None,
        initial_equity: float = INITIAL_EQUITY,
        exit_config: PaperExitConfig | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir = Path(state_dir) if state_dir is not None else self.output_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.exit_config = exit_config or PaperExitConfig()
        (self.output_dir / "paper_trades.jsonl").touch(exist_ok=True)
        if self.state_dir != self.output_dir:
            (self.state_dir / "paper_trades.jsonl").touch(exist_ok=True)
        self.initial_equity = initial_equity
        self.positions: dict[str, PaperPosition] = self._load_positions()
        self.realized_pnl = 0.0
        self.realized_margin_pnl = 0.0
        self.closed_trade_pnls: list[float] = []
        self.closed_trade_margin_pnls: list[float] = []
        self.equity_peak = initial_equity
        self.max_drawdown = 0.0
        self._load_equity()

    def on_decision(
        self,
        *,
        symbol: str,
        decision_payload: Mapping[str, Any],
        draft_payload: Mapping[str, Any],
        kline: Mapping[str, Any],
        timestamp: int,
    ) -> list[str]:
        events: list[str] = []
        if symbol in self.positions:
            events.extend(self._update_position(symbol, kline, timestamp, decision_payload))
        if draft_payload.get("approved") and symbol not in self.positions:
            opened = self._open_position(symbol, decision_payload, draft_payload, kline, timestamp)
            if opened:
                events.append(f"PAPER_OPEN:{symbol}:{opened.side}@{opened.entry_price:.8f}")
        self._write_snapshots(timestamp)
        return events

    def _open_position(
        self,
        symbol: str,
        decision_payload: Mapping[str, Any],
        draft_payload: Mapping[str, Any],
        kline: Mapping[str, Any],
        timestamp: int,
    ) -> PaperPosition | None:
        request = draft_payload.get("request")
        if not isinstance(request, Mapping):
            return None
        price = _positive_float(kline.get("close")) or _positive_float(request.get("price"))
        quantity = _positive_float(request.get("quantity"))
        if price is None or quantity is None:
            return None
        side = str(request.get("position_side") or decision_payload.get("side") or "").upper()
        if side not in {"LONG", "SHORT"}:
            return None
        atr_pct = max(0.0, float(decision_payload.get("entry_context", {}).get("atr_pct") or 0.0))
        stop_pct = max(MIN_STOP_PCT, min(MAX_STOP_PCT, atr_pct * ATR_STOP_MULT if atr_pct > 0 else 0.01))
        risk_distance = price * stop_pct
        stop_price = price - risk_distance if side == "LONG" else price + risk_distance
        tp_prices = [price + risk_distance * level if side == "LONG" else price - risk_distance * level for level in TP_LEVELS]
        notional = price * quantity
        position = PaperPosition(
            symbol=symbol,
            side=side,
            entry_time=timestamp,
            entry_price=price,
            quantity=quantity,
            notional=notional,
            leverage=int(decision_payload.get("leverage") or 1),
            stop_price=stop_price,
            tp_prices=tp_prices,
            tp_fractions=list(TP_FRACTIONS),
            tp_consumed=[],
            remaining_fraction=1.0,
            realized_pnl=-(fee(notional, FEE_BPS) + fee(notional, SLIPPAGE_BPS)),
            realized_margin_pnl=-(fee(notional, FEE_BPS) + fee(notional, SLIPPAGE_BPS)) * int(decision_payload.get("leverage") or 1),
            entry_fee=fee(notional, FEE_BPS),
            entry_slippage=fee(notional, SLIPPAGE_BPS),
            last_price=price,
            best_price=price,
            max_favorable_r_observed=0.0,
            hold_bars=0,
            last_processed_kline_ts=timestamp,
            score=float(decision_payload.get("score") or 0.0),
            reasons=[str(item) for item in decision_payload.get("reasons", [])],
            exit_mode=str(decision_payload.get("exit_mode") or self.exit_config.mode),
            scout_mission=str(decision_payload.get("scout_mission")) if decision_payload.get("scout_mission") else None,
            experiment_id=str(decision_payload.get("experiment_id")) if decision_payload.get("experiment_id") else None,
            entry_channel=str(decision_payload.get("entry_channel")) if decision_payload.get("entry_channel") else None,
            source_quadrant=str(decision_payload.get("source_quadrant") or decision_payload.get("quadrant")) if (decision_payload.get("source_quadrant") or decision_payload.get("quadrant")) else None,
            q3_reduced=False,
            q4_streak=0,
        )
        self.positions[symbol] = position
        self.realized_pnl += position.realized_pnl
        self.realized_margin_pnl += position.realized_margin_pnl
        self._append_trade_event(
            {
                "timestamp": timestamp,
                "event": "PAPER_OPEN",
                "symbol": symbol,
                "side": side,
                "price": price,
                "quantity": quantity,
                "notional": notional,
                "leverage": position.leverage,
                "margin_used": _margin_used(notional, position.leverage),
                "fee": position.entry_fee,
                "slippage": position.entry_slippage,
                "notional_pnl": position.realized_pnl,
                "margin_pnl": position.realized_margin_pnl,
                "pnl_accounting_mode": "notional_primary_margin_reporting",
                "score": position.score,
                "reasons": position.reasons,
                "exit_mode": position.exit_mode,
                "scout_mission": position.scout_mission,
                "experiment_id": position.experiment_id,
                "entry_channel": position.entry_channel,
                "source_quadrant": position.source_quadrant,
                "max_favorable_r_observed": position.max_favorable_r_observed,
            }
        )
        return position

    def _update_position(self, symbol: str, kline: Mapping[str, Any], timestamp: int, decision_payload: Mapping[str, Any] | None = None) -> list[str]:
        position = self.positions[symbol]
        high = _positive_float(kline.get("high"))
        low = _positive_float(kline.get("low"))
        close = _positive_float(kline.get("close"))
        if high is None or low is None or close is None:
            return []
        if timestamp <= position.entry_time or timestamp <= position.last_processed_kline_ts:
            return []

        position.last_price = close
        _update_best_price(position, high, low)
        _update_max_favorable_r_observed(position)
        _apply_early_breakeven(position, self._position_exit_config(position))
        if position.tp_consumed:
            _apply_post_tp_stop(position, self._position_exit_config(position))
        position.hold_bars += 1
        position.last_processed_kline_ts = timestamp
        events: list[str] = []
        if _stop_hit(position.side, high, low, position.stop_price):
            reason = _stop_exit_reason(position)
            net = self._close_fraction(position, timestamp, position.stop_price, position.remaining_fraction, reason)
            events.append(f"PAPER_CLOSE:{symbol}:{reason}:{net:.4f}")
            self.positions.pop(symbol, None)
        else:
            _update_q4_streak(position, decision_payload)
            _apply_q2_stop_tightening(position, decision_payload)
            if _q4_defensive_exit(position, close):
                net = self._close_fraction(position, timestamp, close, position.remaining_fraction, "Q4_DEFENSIVE_EXIT")
                events.append(f"PAPER_CLOSE:{symbol}:Q4_DEFENSIVE_EXIT:{net:.4f}")
                self.positions.pop(symbol, None)
                return events
            if _q3_defensive_reduce(position, decision_payload):
                fraction = min(position.remaining_fraction, 0.5)
                net = self._close_fraction(position, timestamp, close, fraction, "Q3_DEFENSIVE_REDUCE")
                position.q3_reduced = True
                events.append(f"PAPER_REDUCE:{symbol}:Q3_DEFENSIVE_REDUCE:{net:.4f}")
                if position.remaining_fraction <= 0:
                    self.positions.pop(symbol, None)
                return events
            consumed = set(position.tp_consumed)
            for index, tp_price in enumerate(list(position.tp_prices)):
                if position.remaining_fraction <= 0:
                    break
                if index in consumed:
                    continue
                if _tp_hit(position.side, high, low, tp_price):
                    fraction = min(position.remaining_fraction, position.tp_fractions[index])
                    position.tp_consumed.append(index)
                    net = self._close_fraction(position, timestamp, tp_price, fraction, f"TP{index + 1}_HIT")
                    events.append(f"PAPER_REDUCE:{symbol}:TP{index + 1}_HIT:{net:.4f}")
                    if index == 0:
                        _apply_post_tp_stop(position, self._position_exit_config(position))
                    break
            if position.remaining_fraction <= 0:
                self.positions.pop(symbol, None)
            elif _cost_breakeven_timeout(position, close):
                net = self._close_fraction(position, timestamp, close, position.remaining_fraction, "COST_BREAKEVEN_TIMEOUT")
                events.append(f"PAPER_CLOSE:{symbol}:COST_BREAKEVEN_TIMEOUT:{net:.4f}")
                self.positions.pop(symbol, None)
            elif position.hold_bars >= MAX_HOLD_BARS:
                net = self._close_fraction(position, timestamp, close, position.remaining_fraction, "MAX_HOLD_EXIT")
                events.append(f"PAPER_CLOSE:{symbol}:MAX_HOLD_EXIT:{net:.4f}")
                self.positions.pop(symbol, None)
        return events

    def _position_exit_config(self, position: PaperPosition) -> PaperExitConfig:
        return PaperExitConfig(
            mode=position.exit_mode or self.exit_config.mode,
            trend_trigger_r=self.exit_config.trend_trigger_r,
            trailing_r_mult=self.exit_config.trailing_r_mult,
            early_breakeven_enabled=self.exit_config.early_breakeven_enabled,
            early_breakeven_trigger_r=self.exit_config.early_breakeven_trigger_r,
        )

    def _close_fraction(self, position: PaperPosition, timestamp: int, price: float, fraction: float, reason: str) -> float:
        quantity = position.quantity * fraction
        gross = _gross_pnl(position.side, position.entry_price, price, quantity)
        exit_notional = abs(quantity * price)
        exit_fee = fee(exit_notional, FEE_BPS)
        exit_slippage = fee(exit_notional, SLIPPAGE_BPS)
        net = gross - exit_fee - exit_slippage
        margin_net = net * max(1, int(position.leverage))
        position.realized_pnl += net
        position.realized_margin_pnl += margin_net
        position.remaining_fraction = round(max(0.0, position.remaining_fraction - fraction), 10)
        self.realized_pnl += net
        self.realized_margin_pnl += margin_net
        if position.remaining_fraction <= 0:
            self.closed_trade_pnls.append(position.realized_pnl)
            self.closed_trade_margin_pnls.append(position.realized_margin_pnl)
        self._append_trade_event(
            {
                "timestamp": timestamp,
                "event": "PAPER_CLOSE" if position.remaining_fraction <= 0 else "PAPER_REDUCE",
                "symbol": position.symbol,
                "side": position.side,
                "reason": reason,
                "price": price,
                "fraction": fraction,
                "quantity": quantity,
                "leverage": position.leverage,
                "margin_used": _margin_used(position.notional * fraction, position.leverage),
                "gross_pnl": gross,
                "fee": exit_fee,
                "slippage": exit_slippage,
                "net_pnl": net,
                "notional_pnl": net,
                "margin_pnl": margin_net,
                "position_realized_pnl": position.realized_pnl,
                "position_margin_realized_pnl": position.realized_margin_pnl,
                "pnl_accounting_mode": "notional_primary_margin_reporting",
                "remaining_fraction": position.remaining_fraction,
                "exit_mode": position.exit_mode,
                "scout_mission": position.scout_mission,
                "experiment_id": position.experiment_id,
                "entry_channel": position.entry_channel,
                "source_quadrant": position.source_quadrant,
                "max_favorable_r_observed": position.max_favorable_r_observed,
            }
        )
        return net

    def _write_snapshots(self, timestamp: int) -> None:
        updated_at = int(time.time())
        unrealized = self._unrealized_pnl()
        unrealized_margin = self._unrealized_margin_pnl()
        equity = self.initial_equity + self.realized_pnl + unrealized
        margin_equity = self.initial_equity + self.realized_margin_pnl + unrealized_margin
        self.equity_peak = max(self.equity_peak, equity)
        drawdown = 0.0 if self.equity_peak <= 0 else (self.equity_peak - equity) / self.equity_peak
        self.max_drawdown = max(self.max_drawdown, drawdown)
        self._write_json("paper_positions.json", {symbol: asdict(position) for symbol, position in self.positions.items()})
        self._write_json(
            "paper_equity.json",
            {
                "updated_at": updated_at,
                "timestamp": timestamp,
                "latest_kline_timestamp": timestamp,
                "initial_equity": self.initial_equity,
                "equity": equity,
                "margin_equity": margin_equity,
                "realized_pnl": self.realized_pnl,
                "realized_notional_pnl": self.realized_pnl,
                "realized_margin_pnl": self.realized_margin_pnl,
                "unrealized_pnl": unrealized,
                "unrealized_notional_pnl": unrealized,
                "unrealized_margin_pnl": unrealized_margin,
                "equity_peak": self.equity_peak,
                "max_drawdown": self.max_drawdown,
                "open_positions": len(self.positions),
                "pnl_accounting_mode": "notional_primary_margin_reporting",
            },
        )
        self._write_json("paper_summary.json", self.summary(timestamp, equity, updated_at=updated_at))

    def summary(self, timestamp: int, equity: float | None = None, *, updated_at: int | None = None) -> dict[str, Any]:
        equity_value = equity if equity is not None else self.initial_equity + self.realized_pnl + self._unrealized_pnl()
        wins = [item for item in self.closed_trade_pnls if item > 0]
        losses = [item for item in self.closed_trade_pnls if item < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        win_rate = len(wins) / len(self.closed_trade_pnls) if self.closed_trade_pnls else 0.0
        avg_win = gross_profit / len(wins) if wins else 0.0
        avg_loss = gross_loss / len(losses) if losses else 0.0
        actual_payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
        breakeven_payoff_ratio = (1.0 - win_rate) / win_rate if win_rate > 0 else 0.0
        payoff_ratio_health = actual_payoff_ratio / breakeven_payoff_ratio if breakeven_payoff_ratio > 0 else 0.0
        margin_wins = [item for item in self.closed_trade_margin_pnls if item > 0]
        margin_losses = [item for item in self.closed_trade_margin_pnls if item < 0]
        unrealized = self._unrealized_pnl()
        unrealized_margin = self._unrealized_margin_pnl()
        return {
            "updated_at": updated_at if updated_at is not None else int(time.time()),
            "timestamp": timestamp,
            "latest_kline_timestamp": timestamp,
            "initial_equity": self.initial_equity,
            "equity": equity_value,
            "margin_equity": self.initial_equity + self.realized_margin_pnl + unrealized_margin,
            "return_pct": (equity_value - self.initial_equity) / self.initial_equity if self.initial_equity else 0.0,
            "realized_pnl": self.realized_pnl,
            "realized_notional_pnl": self.realized_pnl,
            "realized_margin_pnl": self.realized_margin_pnl,
            "unrealized_pnl": unrealized,
            "unrealized_notional_pnl": unrealized,
            "unrealized_margin_pnl": unrealized_margin,
            "max_drawdown": self.max_drawdown,
            "trade_count": len(self.closed_trade_pnls),
            "open_positions": len(self.positions),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "actual_payoff_ratio": actual_payoff_ratio,
            "breakeven_payoff_ratio": breakeven_payoff_ratio,
            "payoff_ratio_health": payoff_ratio_health,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0),
            "margin_profit_factor": (
                sum(margin_wins) / abs(sum(margin_losses))
                if sum(margin_losses) < 0
                else (sum(margin_wins) if margin_wins else 0.0)
            ),
            "exit_mode": self.exit_config.mode,
            "pnl_accounting_mode": "notional_primary_margin_reporting",
        }

    def recent_closed_trades(
        self,
        symbol: str,
        *,
        reason: str | None = None,
        since_ts: int | None = None,
        until_ts: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized = symbol.strip().upper()
        rows: list[dict[str, Any]] = []
        for row in self._read_trade_events():
            if row.get("event") != "PAPER_CLOSE":
                continue
            if str(row.get("symbol", "")).strip().upper() != normalized:
                continue
            if reason is not None and row.get("reason") != reason:
                continue
            ts = int(row.get("timestamp") or 0)
            if since_ts is not None and ts < since_ts:
                continue
            if until_ts is not None and ts > until_ts:
                continue
            rows.append(row)
        return rows

    def recent_closed_trades_all(
        self,
        *,
        reason: str | None = None,
        since_ts: int | None = None,
        until_ts: int | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in self._read_trade_events():
            if row.get("event") != "PAPER_CLOSE":
                continue
            if reason is not None and row.get("reason") != reason:
                continue
            ts = int(row.get("timestamp") or 0)
            if since_ts is not None and ts < since_ts:
                continue
            if until_ts is not None and ts > until_ts:
                continue
            rows.append(row)
        return rows

    def trade_events(self) -> list[dict[str, Any]]:
        return self._read_trade_events()

    def has_positive_closed_trade(self, symbol: str, *, until_ts: int | None = None) -> bool:
        return any(float(row.get("position_realized_pnl") or row.get("net_pnl") or 0.0) > 0.0 for row in self.recent_closed_trades(symbol, until_ts=until_ts))

    def get_portfolio_state_snapshot(self, timestamp: int | None = None) -> PortfolioStateSnapshot:
        active_symbols = set(self.positions)
        symbol_exposure_pct: dict[str, float] = {}
        long_exposure = 0.0
        short_exposure = 0.0
        equity_base = self.initial_equity if self.initial_equity > 0 else 1.0
        for symbol, position in self.positions.items():
            exposure = position.notional * max(0.0, position.remaining_fraction) / equity_base
            symbol_exposure_pct[symbol] = exposure
            if position.side == "LONG":
                long_exposure += exposure
            elif position.side == "SHORT":
                short_exposure += exposure

        daily_trades_by_symbol: dict[str, int] = {}
        if timestamp is not None:
            day_start = int(timestamp) - (int(timestamp) % 86400)
            day_end = day_start + 86400
            for row in self._read_trade_events():
                if row.get("event") != "PAPER_OPEN":
                    continue
                ts = int(row.get("timestamp") or 0)
                if ts < day_start or ts >= day_end:
                    continue
                symbol = str(row.get("symbol", "")).strip().upper()
                if symbol:
                    daily_trades_by_symbol[symbol] = daily_trades_by_symbol.get(symbol, 0) + 1

        return PortfolioStateSnapshot(
            active_symbols=active_symbols,
            open_position_count=len(active_symbols),
            total_exposure_pct=sum(symbol_exposure_pct.values()),
            same_direction_long_pct=long_exposure,
            same_direction_short_pct=short_exposure,
            daily_trades_by_symbol=daily_trades_by_symbol,
            portfolio_trades_today=sum(daily_trades_by_symbol.values()),
            daily_profit_pct=self.realized_pnl / equity_base,
            symbol_exposure_pct=symbol_exposure_pct,
        )

    def _unrealized_pnl(self) -> float:
        total = 0.0
        for position in self.positions.values():
            fraction = max(0.0, position.remaining_fraction)
            quantity = position.quantity * fraction
            gross = _gross_pnl(position.side, position.entry_price, position.last_price, quantity)
            exit_notional = abs(quantity * position.last_price)
            total += gross - fee(exit_notional, FEE_BPS) - fee(exit_notional, SLIPPAGE_BPS)
        return total

    def _unrealized_margin_pnl(self) -> float:
        total = 0.0
        for position in self.positions.values():
            fraction = max(0.0, position.remaining_fraction)
            quantity = position.quantity * fraction
            gross = _gross_pnl(position.side, position.entry_price, position.last_price, quantity)
            exit_notional = abs(quantity * position.last_price)
            notional_net = gross - fee(exit_notional, FEE_BPS) - fee(exit_notional, SLIPPAGE_BPS)
            total += notional_net * max(1, int(position.leverage))
        return total

    def _load_positions(self) -> dict[str, PaperPosition]:
        path = self.state_dir / "paper_positions.json"
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        positions: dict[str, PaperPosition] = {}
        for symbol, payload in data.items():
            values = dict(payload)
            values.setdefault("tp_consumed", [])
            values.setdefault("best_price", values.get("last_price", values.get("entry_price", 0.0)))
            values.setdefault("max_favorable_r_observed", 0.0)
            values.setdefault("last_processed_kline_ts", values.get("entry_time", 0))
            values.setdefault("realized_margin_pnl", float(values.get("realized_pnl") or 0.0) * max(1, int(values.get("leverage") or 1)))
            values.setdefault("exit_mode", values.get("exit_mode") or self.exit_config.mode)
            values.setdefault("scout_mission", None)
            values.setdefault("experiment_id", None)
            values.setdefault("entry_channel", None)
            values.setdefault("source_quadrant", None)
            values.setdefault("q3_reduced", False)
            values.setdefault("q4_streak", 0)
            positions[symbol] = PaperPosition(**values)
        return positions

    def _load_equity(self) -> None:
        path = self.state_dir / "paper_equity.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.realized_pnl = float(data.get("realized_pnl") or 0.0)
            self.realized_margin_pnl = float(data.get("realized_margin_pnl") or data.get("realized_pnl") or 0.0)
            self.equity_peak = float(data.get("equity_peak") or self.initial_equity)
            self.max_drawdown = float(data.get("max_drawdown") or 0.0)
        trades_path = self.state_dir / "paper_trades.jsonl"
        if trades_path.exists():
            for line in trades_path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                if row.get("event") == "PAPER_CLOSE":
                    self.closed_trade_pnls.append(float(row.get("position_realized_pnl") or row.get("net_pnl") or 0.0))
                    self.closed_trade_margin_pnls.append(
                        float(row.get("position_margin_realized_pnl") or row.get("position_realized_pnl") or row.get("net_pnl") or 0.0)
                    )

    def _read_trade_events(self) -> list[dict[str, Any]]:
        path = self.state_dir / "paper_trades.jsonl"
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        return rows

    def _append_trade_event(self, row: Mapping[str, Any]) -> None:
        payload = dict(row)
        payload.setdefault("recorded_at", int(time.time()))
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        for directory in self._write_dirs():
            with (directory / "paper_trades.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(line)

    def _write_json(self, name: str, payload: Mapping[str, Any]) -> None:
        text = json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True)
        for directory in self._write_dirs():
            (directory / name).write_text(text, encoding="utf-8")

    def _write_dirs(self) -> list[Path]:
        if self.state_dir == self.output_dir:
            return [self.output_dir]
        return [self.state_dir, self.output_dir]


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _gross_pnl(side: str, entry_price: float, exit_price: float, quantity: float) -> float:
    if side == "SHORT":
        return (entry_price - exit_price) * quantity
    return (exit_price - entry_price) * quantity


def _cost_breakeven_timeout(position: PaperPosition, close: float) -> bool:
    if position.hold_bars < COST_BREAKEVEN_CHECK_BARS or position.tp_consumed:
        return False
    fraction = max(0.0, position.remaining_fraction)
    quantity = position.quantity * fraction
    gross = _gross_pnl(position.side, position.entry_price, close, quantity)
    return gross < _round_trip_cost_estimate(position, close) * COST_BREAKEVEN_BUFFER_MULT


def _round_trip_cost_estimate(position: PaperPosition, close: float) -> float:
    fraction = max(0.0, position.remaining_fraction)
    entry_cost = (position.entry_fee + position.entry_slippage) * fraction
    exit_notional = abs(position.quantity * fraction * close)
    exit_cost = fee(exit_notional, FEE_BPS) + fee(exit_notional, SLIPPAGE_BPS)
    return entry_cost + exit_cost


def _update_best_price(position: PaperPosition, high: float, low: float) -> None:
    if position.side == "SHORT":
        position.best_price = min(position.best_price, low)
    else:
        position.best_price = max(position.best_price, high)


def _update_max_favorable_r_observed(position: PaperPosition) -> None:
    risk_distance = _initial_risk_distance(position)
    if risk_distance <= 0:
        return
    favorable_r = abs(position.best_price - position.entry_price) / risk_distance
    position.max_favorable_r_observed = max(position.max_favorable_r_observed, favorable_r)


def _update_q4_streak(position: PaperPosition, decision_payload: Mapping[str, Any] | None) -> None:
    quadrant = ""
    if isinstance(decision_payload, Mapping):
        quadrant = str(decision_payload.get("quadrant") or "").upper()
    if quadrant == "Q4":
        position.q4_streak += 1
    elif quadrant:
        position.q4_streak = 0


def _q4_defensive_exit(position: PaperPosition, close: float) -> bool:
    if not position.experiment_id:
        return False
    if position.q4_streak < 2:
        return False
    fraction = max(0.0, position.remaining_fraction)
    quantity = position.quantity * fraction
    gross = _gross_pnl(position.side, position.entry_price, close, quantity)
    exit_notional = abs(quantity * close)
    net = gross - fee(exit_notional, FEE_BPS) - fee(exit_notional, SLIPPAGE_BPS)
    return net < 0.0


def _apply_q2_stop_tightening(position: PaperPosition, decision_payload: Mapping[str, Any] | None) -> None:
    if not position.experiment_id or _payload_quadrant(decision_payload) != "Q2":
        return
    breakeven = _breakeven_stop(position)
    if position.side == "SHORT":
        position.stop_price = min(position.stop_price, breakeven)
    else:
        position.stop_price = max(position.stop_price, breakeven)


def _q3_defensive_reduce(position: PaperPosition, decision_payload: Mapping[str, Any] | None) -> bool:
    if not position.experiment_id:
        return False
    if position.q3_reduced:
        return False
    if _payload_quadrant(decision_payload) != "Q3":
        return False
    return position.remaining_fraction > 0.0


def _payload_quadrant(decision_payload: Mapping[str, Any] | None) -> str:
    if not isinstance(decision_payload, Mapping):
        return ""
    return str(decision_payload.get("quadrant") or "").upper()


def _apply_early_breakeven(position: PaperPosition, config: PaperExitConfig) -> None:
    """Payoff 试点: 未触发 TP 时, 一旦达到 early_breakeven_trigger_r 即把止损移到成本(带 buffer)。

    仅当 config.early_breakeven_enabled=True 时生效(试点仅 trend_capture_mirror 分支)。
    已 TP 的仓位交给 _apply_post_tp_stop; 止损只收紧不放宽(LONG 取 max, SHORT 取 min)。
    """
    if not config.early_breakeven_enabled:
        return
    if position.tp_consumed:
        return
    if position.max_favorable_r_observed < max(0.0, config.early_breakeven_trigger_r):
        return
    be = _breakeven_stop(position)
    if position.side == "LONG":
        if position.stop_price < be:
            position.stop_price = be
    else:
        if position.stop_price > be:
            position.stop_price = be


def _apply_post_tp_stop(position: PaperPosition, config: PaperExitConfig) -> None:
    if config.mode != "trend_capture":
        position.stop_price = _breakeven_stop(position)
        return
    risk_distance = _initial_risk_distance(position)
    if risk_distance <= 0:
        position.stop_price = _breakeven_stop(position)
        return
    favorable_r = position.max_favorable_r_observed
    if favorable_r < max(0.0, config.trend_trigger_r):
        position.stop_price = _breakeven_stop(position)
        return
    trailing_distance = risk_distance * max(0.0, config.trailing_r_mult)
    if position.side == "SHORT":
        trailed = position.best_price + trailing_distance
        position.stop_price = min(position.stop_price, trailed)
    else:
        trailed = position.best_price - trailing_distance
        position.stop_price = max(position.stop_price, trailed)


def _breakeven_stop(position: PaperPosition) -> float:
    return position.entry_price * (1.001 if position.side == "LONG" else 0.999)


def _initial_risk_distance(position: PaperPosition) -> float:
    if not position.tp_prices:
        return 0.0
    return abs(position.tp_prices[0] - position.entry_price) / TP_LEVELS[0]


def _margin_used(notional: float, leverage: int) -> float:
    return notional / max(1, int(leverage))


def _stop_hit(side: str, high: float, low: float, stop_price: float) -> bool:
    if side == "SHORT":
        return high >= stop_price
    return low <= stop_price


def _tp_hit(side: str, high: float, low: float, tp_price: float) -> bool:
    if side == "SHORT":
        return low <= tp_price
    return high >= tp_price


def _stop_exit_reason(position: PaperPosition) -> str:
    return "BREAKEVEN_STOP_HIT" if position.tp_consumed else "INITIAL_STOP_HIT"
