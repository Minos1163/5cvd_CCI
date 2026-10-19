"""账本成本核对(2026-10-19): 钉死「手续费+滑点 = 20.98」的双重口径错误。

背景
----
`docs/analysis/2026-10-04_to_10-18_loss_attribution.md` 第 37/162 行把
「手续费 + 滑点 = 20.98 USDT / 31 笔」当成实测摩擦成本。这个数字错了两次:

1. **同一个 5bps 被算了两次。** `fee` 与 `slippage` 由同一函数、同一常量
   (`FEE_BPS = SLIPPAGE_BPS = 5.0`) 生成, 逐行相等; `fee + slippage` 不是两种成本之和。
2. **只统计了 `PAPER_CLOSE` 一条腿。** 同一窗口还有 31 条 `PAPER_OPEN` 与 11 条
   `PAPER_REDUCE`, 它们的 `fee` 同样落账, 被漏掉。

本脚本用账本原始事件重算三条腿的落账成本, 并把旧口径(20.98)精确复现出来作对照,
避免后续分析继续引用它。

产出
----
  cost_ledger.csv            逐事件明细(窗口内, 按 ts 升序)
  by_symbol_quantiles.csv    按标的的成本/R 分位数(窗口内出场, 配对用全历史 FIFO)
  reconciliation.json        {"window": ..., "full": ...} 两段对账

用法
----
  python scripts/analysis/ledger_audit_20261019.py \
    --trades "D:/AIDCA/AI300/logs/*/*/paper_trades.jsonl" \
    --window 1791156600:1792328405 \
    --out D:/AIDCA/AI300/reports/analysis/cost-audit-20261019
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fwdlib.ledger import (  # noqa: E402
    RISK_PCT_PROXY,
    attribute_legs,
    load_trade_events,
    reconcile,
    symbol_quantiles,
)

#: 默认路径相对**仓库根**解析(worktree 里就是本仓库),换机器不会写死到别人的盘符;
#: 环境变量 ``FWD_LOGS`` / ``FWD_REPORTS`` 优先,便于把产物指回主工作区。
REPO_ROOT = Path(__file__).resolve().parents[2]


def _default_logs() -> str:
    return os.environ.get("FWD_LOGS") or str(REPO_ROOT / "logs")


def _default_out(slug: str) -> str:
    base = os.environ.get("FWD_REPORTS")
    return str(Path(base) / slug) if base else str(REPO_ROOT / "reports" / "analysis" / slug)


DEFAULT_TRADES = str(Path(_default_logs()) / "*" / "*" / "paper_trades.jsonl")
DEFAULT_OUT = _default_out("cost-audit-20261019")

LEDGER_FIELDS = [
    "event",
    "kind",
    "symbol",
    "side",
    "ts",
    "price",
    "quantity",
    "notional",
    "fee",
    "slippage",
    "fee_bps",
    "slip_bps",
    "reason",
]

QUANTILE_FIELDS = [
    "symbol",
    "n",
    "fee_bps_p50",
    "slip_bps_p50",
    "notional_p50",
    "notional_p90",
    "r_multiple_mean",
    "r_multiple_p50",
]


def _parse_window(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) != 2:
        raise SystemExit(f"bad --window {raw!r}, expected 't0:t1'")
    return int(parts[0]), int(parts[1])


def _write_ledger_csv(path: Path, events: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=LEDGER_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for ev in events:
            writer.writerow(
                {
                    "event": ev["event"],
                    "kind": ev["kind"],
                    "symbol": ev["symbol"],
                    "side": ev["side"],
                    "ts": ev["ts"],
                    "price": round(ev["price"], 8),
                    "quantity": round(ev["quantity"], 8),
                    "notional": round(ev["notional"], 6),
                    "fee": round(ev["fee"], 6),
                    "slippage": round(ev["slippage"], 6),
                    "fee_bps": ev["fee_bps"],
                    "slip_bps": ev["slip_bps"],
                    "reason": ev["reason"],
                }
            )


def _write_quantiles_csv(path: Path, quantiles: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=QUANTILE_FIELDS)
        writer.writeheader()
        for symbol, row in quantiles.items():
            writer.writerow({"symbol": symbol, **row})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="纸面账本成本核对(分腿 + 隐含 bps)")
    parser.add_argument("--trades", default=DEFAULT_TRADES, help="paper_trades.jsonl 的 glob")
    parser.add_argument("--window", default=None, help="闭区间 t0:t1 (unix 秒)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="输出目录")
    args = parser.parse_args(argv)

    window = _parse_window(args.window)

    files = sorted(glob.glob(args.trades, recursive=True))
    events = load_trade_events([args.trades])
    print(f"[ledger] files={len(files)} events={len(events)}")
    if not events:
        raise SystemExit("no trade events")

    full = reconcile(events)
    window_rec = reconcile(events, window=window) if window is not None else full
    selected = (
        [e for e in events if window[0] <= e["ts"] <= window[1]]
        if window is not None
        else list(events)
    )

    attributed_all = attribute_legs(events)
    if window is not None:
        attributed = [a for a in attributed_all if window[0] <= a["exit_time"] <= window[1]]
    else:
        attributed = attributed_all
    quantiles = symbol_quantiles(attributed)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_ledger_csv(out_dir / "cost_ledger.csv", selected)
    _write_quantiles_csv(out_dir / "by_symbol_quantiles.csv", quantiles)
    payload = {"window": window_rec, "full": full}
    with open(out_dir / "reconciliation.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    w = window_rec
    print(f"[ledger] 腿数 open={w['n_open']} reduce={w['n_reduce']} close={w['n_close']}")
    print(
        "[ledger] fee_total={:.4f} slip_total={:.4f} (fee==slip {:.0%})".format(
            w["fee_total"], w["slip_total"], w["fee_equals_slip_share"]
        )
    )
    print(
        "[ledger] implied_bps fee_only={:.4f} fee+slip={:.4f}  fee_bps_values={}".format(
            w["implied_bps_fee_only"], w["implied_bps_fee_plus_slip"], w["fee_bps_values"]
        )
    )
    print(
        "[ledger] legacy(close only)={:.4f}  correct_fee_only={:.4f}  fee+slip={:.4f}".format(
            w["legacy_attribution"],
            w["correct_fee_only"],
            w["double_count_if_slip_is_real"],
        )
    )
    matched = sum(1 for a in attributed if a["match_ok"])
    rate = matched / len(attributed) if attributed else 0.0
    print(
        f"[ledger] legs={len(attributed)} match_ok={matched} rate={rate:.4f} "
        f"(R 按 {RISK_PCT_PROXY:.0%} 名义价差代理)"
    )
    print(f"[ledger] wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
