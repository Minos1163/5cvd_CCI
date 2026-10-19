"""纸面账本（`paper_trades.jsonl`）的成本核对与分腿归因。

为什么要有这个模块
------------------
归因文档 `2026-10-04_to_10-18_loss_attribution.md` 把「手续费 + 滑点 = 20.98 USDT」
当成实测摩擦成本, 这个数字有**两处口径错误**:

1. **同一个 5bps 被算了两次。** 线上账本里 `fee` 与 `slippage` 由同一函数、同一常量
   (`FEE_BPS = SLIPPAGE_BPS = 5.0`) 生成, 两列数值逐行相同。`fee + slippage` 不是
   「手续费 + 滑点」, 而是「手续费 × 2」(若把滑点当真实成本) 或「手续费 + 冗余列」。
2. **只覆盖了 `PAPER_CLOSE` 一条腿。** 10-04→10-18 窗口内还有 31 条 `PAPER_OPEN`
   与 11 条 `PAPER_REDUCE`, 它们的 `fee` 同样落账。只对 close 求和, 漏掉了
   11.4981 (open) + 1.0488 (reduce)。

本模块把「事件 → 分腿 → 可复算的 bps」这条链钉死, 供任何后续分析复用:

- `load_trade_events`  读日志并标准化字段(不依赖 pandas)。
- `reconcile`          按事件类型分腿合计, 反算隐含 bps, 并给出旧口径(20.98)的复现值。
- `attribute_legs`     按 symbol 做 FIFO, 为每笔出场配对入场价/入场时间。
- `symbol_quantiles`   按标的给出成本与 R 的分位数, 用于判断成本是否集中在少数标的。

R 的口径说明
------------
账本没有 `stop_pct` 字段(它在 `attribution.jsonl` 的 `entry_context` 里, 本模块只读
`paper_trades.jsonl`), 因此 `r_multiple` 统一按 **1% 名义价差 = 1R** 折算。这只是一个
跨笔可比、可复算的粗量级, 与归因文档里用真实 `stop_pct`(0.5%–3%)算出的 R **不可直接
对比**; 若需要真实 R, 应另接 `attribution.jsonl`。
"""

from __future__ import annotations

import glob as _glob
import json
import math
import statistics
from collections import defaultdict, deque
from pathlib import Path

from .config import FEE_BPS, SLIPPAGE_BPS

__all__ = [
    "RISK_PCT_PROXY",
    "attribute_legs",
    "load_trade_events",
    "reconcile",
    "symbol_quantiles",
]

# 账本缺 stop_pct: 用 1% 名义价差作为 1R 的统一代理(仅作量级比较)。
RISK_PCT_PROXY = 0.01

_KIND_BY_EVENT = {
    "PAPER_OPEN": "open",
    "PAPER_REDUCE": "reduce",
    "PAPER_CLOSE": "close",
}

_BPS_TOL = 1e-12


def _f(row: dict, key: str, default: float = 0.0) -> float:
    try:
        v = row.get(key)
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def _round(x: float, nd: int = 6) -> float:
    return round(float(x), nd)


def _expand_globs(globs) -> list[str]:
    if isinstance(globs, (str, Path)):
        globs = [globs]
    files: list[str] = []
    seen: set[str] = set()
    for pattern in globs:
        for path in sorted(_glob.glob(str(pattern), recursive=True)):
            key = str(Path(path).resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            files.append(path)
    return files


def load_trade_events(globs) -> list[dict]:
    """读取 `paper_trades.jsonl` 并标准化为事件字典列表。

    参数
    ----
    globs : str | Path | list[str | Path]
        glob 模式, 例如 ``logs/*/*/paper_trades.jsonl``。

    返回
    ----
    list[dict], 按 ``(ts, recorded_at)`` 升序。每项键:
        event, kind(open|reduce|close), symbol, side, ts, price, quantity,
        notional, fee, slippage, fee_bps, slip_bps, reason, fraction
    另附 ``gross_pnl`` / ``recorded_at`` 供 `attribute_legs` 使用。
    """
    events: list[dict] = []
    for path in _expand_globs(globs):
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event = str(row.get("event") or "")
                kind = _KIND_BY_EVENT.get(event)
                if kind is None:
                    continue

                price = _f(row, "price")
                quantity = _f(row, "quantity")
                gross_notional = abs(price * quantity)
                if kind == "open":
                    notional = _f(row, "notional") or gross_notional
                else:
                    notional = gross_notional

                fee = _f(row, "fee")
                slippage = _f(row, "slippage")
                fee_bps = fee / gross_notional * 1e4 if gross_notional > 0 else 0.0
                slip_bps = slippage / gross_notional * 1e4 if gross_notional > 0 else 0.0

                reason = row.get("reason")
                if reason is None:
                    reasons = row.get("reasons")
                    if isinstance(reasons, (list, tuple)):
                        reason = "|".join(str(r) for r in reasons)
                    elif reasons:
                        reason = str(reasons)
                reason = reason or ""

                ts = row.get("timestamp")
                if ts is None:
                    ts = row.get("recorded_at")
                ts = int(ts) if ts is not None else 0

                events.append(
                    {
                        "event": event,
                        "kind": kind,
                        "symbol": str(row.get("symbol") or ""),
                        "side": str(row.get("side") or ""),
                        "ts": ts,
                        "price": price,
                        "quantity": quantity,
                        "notional": notional,
                        "fee": fee,
                        "slippage": slippage,
                        "fee_bps": _round(fee_bps, 6),
                        "slip_bps": _round(slip_bps, 6),
                        "reason": reason,
                        "fraction": _f(row, "fraction", 1.0),
                        "gross_pnl": _f(row, "gross_pnl"),
                        "recorded_at": int(_f(row, "recorded_at", ts)),
                    }
                )

    events.sort(key=lambda e: (e["ts"], e["recorded_at"]))
    return events


def _select(events: list[dict], window) -> list[dict]:
    if window is None:
        return list(events)
    t0, t1 = float(window[0]), float(window[1])
    return [e for e in events if t0 <= e["ts"] <= t1]


def reconcile(events, *, window=None) -> dict:
    """按事件类型分腿合计, 并给出隐含往返 bps 与旧口径的复现值。

    `window` 为 ``(t0, t1)`` 闭区间; 为 None 时统计全量。
    """
    selected = _select(list(events), window)

    by_event = {
        kind: {"n": 0, "fee": 0.0, "slip": 0.0, "notional": 0.0}
        for kind in ("open", "reduce", "close")
    }
    fee_total = 0.0
    slip_total = 0.0
    entry_notional = 0.0
    fee_eq_slip = 0
    fee_bps_values: set[float] = set()

    for ev in selected:
        bucket = by_event[ev["kind"]]
        bucket["n"] += 1
        bucket["fee"] += ev["fee"]
        bucket["slip"] += ev["slippage"]
        bucket["notional"] += ev["notional"]

        fee_total += ev["fee"]
        slip_total += ev["slippage"]
        if ev["kind"] == "open":
            entry_notional += ev["notional"]

        if abs(ev["fee"] - ev["slippage"]) <= _BPS_TOL * max(1.0, abs(ev["fee"])):
            fee_eq_slip += 1

        if ev["fee"] and ev["price"] * ev["quantity"]:
            fee_bps_values.add(_round(ev["fee"] / (ev["price"] * ev["quantity"]) * 1e4, 6))

    close_fee = by_event["close"]["fee"]
    close_slip = by_event["close"]["slip"]

    if window is not None:
        span = [int(window[0]), int(window[1])]
    elif selected:
        span = [selected[0]["ts"], selected[-1]["ts"]]
    else:
        span = [None, None]

    return {
        "n_events": len(selected),
        "n_open": by_event["open"]["n"],
        "n_reduce": by_event["reduce"]["n"],
        "n_close": by_event["close"]["n"],
        "by_event": {
            kind: {
                "n": bucket["n"],
                "fee": _round(bucket["fee"]),
                "slip": _round(bucket["slip"]),
                "notional": _round(bucket["notional"]),
            }
            for kind, bucket in by_event.items()
        },
        "fee_total": _round(fee_total),
        "slip_total": _round(slip_total),
        "fee_equals_slip_share": _round(fee_eq_slip / len(selected), 6) if selected else 0.0,
        "fee_bps_values": sorted(fee_bps_values),
        "implied_bps_fee_only": (
            _round(fee_total / entry_notional * 1e4) if entry_notional else 0.0
        ),
        "implied_bps_fee_plus_slip": (
            _round((fee_total + slip_total) / entry_notional * 1e4) if entry_notional else 0.0
        ),
        "entry_notional": _round(entry_notional),
        "legacy_attribution": _round(close_fee + close_slip),
        "correct_fee_only": _round(fee_total),
        "double_count_if_slip_is_real": _round(fee_total + slip_total),
        "config_fee_bps": FEE_BPS,
        "config_slip_bps": SLIPPAGE_BPS,
        "window": [int(span[0]) if span[0] is not None else None,
                   int(span[1]) if span[1] is not None else None],
        "n_close_in_window": by_event["close"]["n"],
        "n_close_all": sum(1 for e in events if e["kind"] == "close"),
    }


def attribute_legs(events) -> list[dict]:
    """按 symbol 做 FIFO 配对, 每笔出场事件返回一条分腿记录。

    - 持仓队列按 ``(ts, recorded_at)`` 顺序消费; 部分减仓会按比例消耗最早的开仓。
    - **重开仓即替换**: 账本对同一标的同时只维护一个持仓, 若旧持仓未平就收到新的
      `PAPER_OPEN`, 引擎直接覆盖(不写 close 行)。此时旧批次已成幽灵, 若不丢弃,
      平仓行会被配到更早的价格上。实测纯 FIFO 有 8/340 笔对不上(全部集中在 6 月
      ZEC/XLM 这类重开仓), 重置后 340/340 全部自洽。
    - ``entry_price`` 优先用 FIFO 配到的开仓价(多批次按数量加权); 若队列为空
      (窗口截断导致 open 缺失), 用 ``gross_pnl`` 反推:
      LONG ``entry = exit - gross/qty``; SHORT ``entry = exit + gross/qty``。
    - ``match_ok``: 反推价与 FIFO 记录价的相对误差 < 1e-6 为 True;
      无 FIFO 记录但反推成功时亦为 True。
    """
    ordered = sorted(events, key=lambda e: (e["ts"], e["recorded_at"]))
    books: dict[str, deque] = defaultdict(deque)
    legs: list[dict] = []

    for ev in ordered:
        if ev["kind"] == "open":
            if books[ev["symbol"]]:
                # 旧持仓未平就被覆盖: 账本不会补 close 行, 这些批次是幽灵。
                books[ev["symbol"]].clear()
            books[ev["symbol"]].append(
                {
                    "price": ev["price"],
                    "qty": ev["quantity"],
                    "remaining": ev["quantity"],
                    "ts": ev["ts"],
                }
            )
            continue

        symbol = ev["symbol"]
        qty = ev["quantity"]
        book = books[symbol]

        matched_qty = 0.0
        weighted_entry = 0.0
        entry_ts: int | None = None
        need = qty
        while need > 1e-12 and book:
            lot = book[0]
            take = min(need, lot["remaining"])
            weighted_entry += lot["price"] * take
            matched_qty += take
            if entry_ts is None:
                entry_ts = lot["ts"]
            lot["remaining"] -= take
            need -= take
            if lot["remaining"] <= 1e-12:
                book.popleft()

        fifo_entry = weighted_entry / matched_qty if matched_qty > 0 else None

        gross = ev["gross_pnl"]
        reversed_entry = None
        if qty > 0:
            if ev["side"] == "SHORT":
                reversed_entry = ev["price"] + gross / qty
            else:
                reversed_entry = ev["price"] - gross / qty

        if fifo_entry is not None and reversed_entry is not None:
            match_ok = abs(reversed_entry - fifo_entry) <= 1e-6 * max(1.0, abs(fifo_entry))
        else:
            match_ok = fifo_entry is not None or reversed_entry is not None

        entry_price = fifo_entry if fifo_entry is not None else (reversed_entry or 0.0)

        notional = abs(ev["price"] * qty)
        risk = notional * RISK_PCT_PROXY
        legs.append(
            {
                "symbol": symbol,
                "side": ev["side"],
                "entry_price": _round(entry_price, 8),
                "entry_time": int(entry_ts) if entry_ts is not None else None,
                "exit_price": _round(ev["price"], 8),
                "exit_time": ev["ts"],
                "gross_pnl": _round(gross),
                "notional": _round(notional),
                "fee": _round(ev["fee"]),
                "slippage": _round(ev["slippage"]),
                "fee_bps": ev["fee_bps"],
                "slip_bps": ev["slip_bps"],
                "r_multiple": _round(gross / risk, 6) if risk else 0.0,
                "match_ok": bool(match_ok),
            }
        )

    return legs


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    data = sorted(values)
    if len(data) == 1:
        return float(data[0])
    pos = (len(data) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(data[lo])
    return float(data[lo] + (data[hi] - data[lo]) * (pos - lo))


def symbol_quantiles(attributed) -> dict:
    """按标的汇总成本与 R 的分位数(中位数/P90)。"""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for leg in attributed:
        grouped[leg["symbol"]].append(leg)

    out: dict[str, dict] = {}
    for symbol, legs in sorted(grouped.items()):
        notionals = [float(x["notional"]) for x in legs]
        rs = [float(x["r_multiple"]) for x in legs]
        out[symbol] = {
            "n": len(legs),
            "fee_bps_p50": _round(statistics.median(x["fee_bps"] for x in legs), 6),
            "slip_bps_p50": _round(statistics.median(x["slip_bps"] for x in legs), 6),
            "notional_p50": _round(_quantile(notionals, 0.5)),
            "notional_p90": _round(_quantile(notionals, 0.9)),
            "r_multiple_mean": _round(statistics.fmean(rs), 6),
            "r_multiple_p50": _round(_quantile(rs, 0.5), 6),
        }
    return out
