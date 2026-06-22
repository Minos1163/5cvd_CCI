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
TP_LEVELS = (1.0, 2.0, 3.0)
TP_FRACTIONS = (0.40, 0.35, 0.25)


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
    hold_bars: int
    last_processed_kline_ts: int
    score: float
    reasons: list[str]


class PaperTradingLedger:
    def __init__(
        self,
        output_dir: str | Path,
        *,
        state_dir: str | Path | None = None,
        initial_equity: float = INITIAL_EQUITY,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir = Path(state_dir) if state_dir is not None else self.output_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
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
            events.extend(self._update_position(symbol, kline, timestamp))
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
            hold_bars=0,
            last_processed_kline_ts=timestamp,
            score=float(decision_payload.get("score") or 0.0),
            reasons=[str(item) for item in decision_payload.get("reasons", [])],
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
            }
        )
        return position

    def _update_position(self, symbol: str, kline: Mapping[str, Any], timestamp: int) -> list[str]:
        position = self.positions[symbol]
        high = _positive_float(kline.get("high"))
        low = _positive_float(kline.get("low"))
        close = _positive_float(kline.get("close"))
        if high is None or low is None or close is None:
            return []
        if timestamp <= position.entry_time or timestamp <= position.last_processed_kline_ts:
            return []

        position.last_price = close
        position.hold_bars += 1
        position.last_processed_kline_ts = timestamp
        events: list[str] = []
        if _stop_hit(position.side, high, low, position.stop_price):
            net = self._close_fraction(position, timestamp, position.stop_price, position.remaining_fraction, "STOP_HIT")
            events.append(f"PAPER_CLOSE:{symbol}:STOP_HIT:{net:.4f}")
            self.positions.pop(symbol, None)
        else:
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
                        position.stop_price = position.entry_price * (1.001 if position.side == "LONG" else 0.999)
                    break
            if position.remaining_fraction <= 0:
                self.positions.pop(symbol, None)
            elif position.hold_bars >= MAX_HOLD_BARS:
                net = self._close_fraction(position, timestamp, close, position.remaining_fraction, "MAX_HOLD_EXIT")
                events.append(f"PAPER_CLOSE:{symbol}:MAX_HOLD_EXIT:{net:.4f}")
                self.positions.pop(symbol, None)
        return events

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
            "win_rate": len(wins) / len(self.closed_trade_pnls) if self.closed_trade_pnls else 0.0,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0),
            "margin_profit_factor": (
                sum(margin_wins) / abs(sum(margin_losses))
                if sum(margin_losses) < 0
                else (sum(margin_wins) if margin_wins else 0.0)
            ),
            "pnl_accounting_mode": "notional_primary_margin_reporting",
        }

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
            values.setdefault("last_processed_kline_ts", values.get("entry_time", 0))
            values.setdefault("realized_margin_pnl", float(values.get("realized_pnl") or 0.0) * max(1, int(values.get("leverage") or 1)))
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
