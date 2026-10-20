"""长历史候选复核:对指定"方向规则 × 持有期"做按年、按方向、按成本的分层。

用途
----
`long_history_probe_20261020.py` 只回答"哪一格均值最高"。本脚本回答四个更要命的问题:

1. **是按年稳定的,还是某一年撑起来的?**(regime 依赖)
2. **多头腿还是空头腿赚的?** 5 年牛市里若只有多头腿贡献,那大概率是 beta,
   而不是方向规则。
3. **扣掉换手成本后,复利权益曲线还为正吗?**(每次调仓 = 一次往返)
4. **有效片段够不够 G1′ 的 2,000?**

口径
----
- 方向在 `t` 收盘定,`t+1` 开盘换仓,持有 `horizon` 根(4h)后下次换仓;
- 换手成本按**每次换仓一次往返**扣(同一方向继续持有时不扣);
- 收益按 bps 计;`基准` = 同区间永远做多。

用法
----
    python scripts/analysis/long_history_candidate_20261020.py --rule sma50_200 --horizon 42
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

CACHE = ROOT / "data" / "history"
REPORT_ROOT = ROOT / "logs" / "analysis" / "long-history"
INTERVAL = "4h"
BAR_HOURS = 4


def prepare(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("ts").reset_index(drop=True)
    close = df["close"]
    df["ema200"] = close.ewm(span=200, adjust=False).mean()
    df["sma50"] = close.rolling(50).mean()
    df["sma200"] = close.rolling(200).mean()
    df["donch_mid"] = (df["high"].rolling(20).max() + df["low"].rolling(20).min()) / 2.0
    df["mom6"] = close / close.shift(6) - 1.0
    df["date"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.strftime("%Y-%m-%d")
    df["year"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.year
    df["dir_ema200"] = (close - df["ema200"]).apply(lambda v: 1 if v > 0 else (-1 if v < 0 else 0))
    df["dir_sma50_200"] = (df["sma50"] - df["sma200"]).apply(lambda v: 1 if v > 0 else (-1 if v < 0 else 0))
    df["dir_donch20"] = (close - df["donch_mid"]).apply(lambda v: 1 if v > 0 else (-1 if v < 0 else 0))
    df["dir_mom6"] = df["mom6"].apply(lambda v: 1 if v > 0 else (-1 if v < 0 else 0))
    return df


def run_symbol(symbol: str, df: pd.DataFrame, rule: str, horizon: int, cost_bps: float) -> dict:
    entry = df["open"].shift(-1)
    exit_ = df["open"].shift(-(1 + horizon))
    fwd = (exit_ / entry - 1.0) * 1e4
    direction = df[f"dir_{rule}"]

    # 只在换仓点取样:每 horizon 根一个,保证不重叠
    idx = [i for i in df.index if i % horizon == 0 and
           direction.notna().iloc[i] and fwd.notna().iloc[i] and direction.iloc[i] != 0]
    if not idx:
        return {}
    rows = []
    prev_dir = None
    for i in idx:
        value = float(direction.iloc[i] * fwd.iloc[i])
        turnover = 0.0 if prev_dir == direction.iloc[i] else 1.0
        prev_dir = direction.iloc[i]
        rows.append({"year": int(df.at[i, "year"]), "dir": int(direction.iloc[i]),
                     "gross": value, "cost": turnover * cost_bps,
                     "net": value - turnover * cost_bps})
    frame = pd.DataFrame(rows)

    def _agg(sub: pd.DataFrame) -> dict:
        if sub.empty:
            return {}
        return {"n": int(len(sub)), "gross": float(sub["gross"].mean()),
                "net": float(sub["net"].mean()),
                "sd": float(sub["gross"].std(ddof=1)) if len(sub) > 2 else None,
                "t": float(sub["gross"].mean() / (sub["gross"].std(ddof=1) / math.sqrt(len(sub))))
                if len(sub) > 2 and sub["gross"].std(ddof=1) > 0 else None}

    base_idx = [i for i in df.index if i % horizon == 0 and fwd.notna().iloc[i]]
    base = float(fwd.loc[base_idx].mean()) if base_idx else float("nan")
    overall = _agg(frame)
    if not overall:
        return {}
    overall["base"] = base
    overall["excess"] = overall["gross"] - base
    by_year = {int(y): _agg(g) for y, g in frame.groupby("year")}
    by_side = {int(d): _agg(g) for d, g in frame.groupby("dir")}
    # 复利:每笔按净 bps 作用于权益
    equity = 1.0
    for value in frame["net"]:
        equity *= (1.0 + value / 1e4)
    return {"symbol": symbol, "rule": rule, "horizon": horizon,
            "overall": overall, "by_year": by_year, "by_side": by_side,
            "equity_multiple": equity, "days": int(frame.shape[0])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", default="sma50_200")
    ap.add_argument("--horizon", type=int, default=42)
    ap.add_argument("--cost", type=float, default=20.0)
    ap.add_argument("--symbols", default="")
    ap.add_argument("--date", default="2026-10-20")
    args = ap.parse_args()

    files = sorted(CACHE.glob(f"*_{INTERVAL}.csv"))
    if args.symbols:
        wanted = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
        files = [p for p in files if p.stem.split("_")[0] in wanted]
    if not files:
        raise SystemExit("no cache; run long_history_probe_20261020.py first")

    results = []
    for path in files:
        symbol = path.stem.split("_")[0]
        df = prepare(path)
        if len(df) < 500:
            continue
        item = run_symbol(symbol, df, args.rule, args.horizon, args.cost)
        if item:
            results.append(item)

    if not results:
        raise SystemExit("no results")

    lines = [f"# 候选复核:{args.rule} / 持有 {args.horizon} 根(≈{args.horizon*BAR_HOURS/24:.1f} 天)", "",
             f"- 成本:每次换仓 {args.cost:.0f}bps 往返", "- 口径:t 收盘定方向,t+1 开盘换仓,非重叠取样", ""]
    lines.append("## 1. 分品种")
    lines.append("")
    lines.append("| 品种 | n | 毛 bps | 基准 | 超额 | 净 bps | t(毛) | 复利倍数 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for item in results:
        o = item["overall"]
        lines.append(f"| {item['symbol']} | {o['n']} | {o['gross']:+.1f} | {o['base']:+.1f} | "
                     f"{o['excess']:+.1f} | {o['net']:+.1f} | "
                     f"{(o['t'] if o['t'] is not None else float('nan')):+.2f} | {item['equity_multiple']:.3f} |")
    lines.append("")

    def _avg(key: str) -> float:
        return statistics.fmean([it["overall"][key] for it in results])

    positives = sum(1 for it in results if it["overall"]["excess"] > 0)
    lines.append(f"- 等权平均:毛 **{_avg('gross'):+.1f} bps** / 基准 {_avg('base'):+.1f} / "
                 f"超额 **{_avg('excess'):+.1f}** / 净 **{_avg('net'):+.1f}**")
    lines.append(f"- 超额为正的品种:**{positives}/{len(results)}**")
    lines.append(f"- 有效片段合计:`{sum(it['overall']['n'] for it in results)}`")
    lines.append("")

    lines.append("## 2. 按年(等权平均 毛 / 净 bps)")
    lines.append("")
    years = sorted({y for it in results for y in it["by_year"]})
    lines.append("| 年份 | 品种数 | 毛 bps | 净 bps | 超额为正品种 |")
    lines.append("|---|---:|---:|---:|---:|")
    for year in years:
        vals = [(it["by_year"][year], it["overall"]["base"]) for it in results if year in it["by_year"]]
        if not vals:
            continue
        gross = statistics.fmean([v[0]["gross"] for v in vals])
        net = statistics.fmean([v[0]["net"] for v in vals])
        pos = sum(1 for v in vals if v[0]["gross"] > v[1])
        lines.append(f"| {year} | {len(vals)} | {gross:+.1f} | {net:+.1f} | {pos}/{len(vals)} |")
    lines.append("")

    lines.append("## 3. 按方向(等权平均)")
    lines.append("")
    lines.append("| 方向 | 片段数 | 毛 bps | t |")
    lines.append("|---|---:|---:|---:|")
    for side, label in ((1, "LONG"), (-1, "SHORT")):
        sub = [it["by_side"][side] for it in results if side in it["by_side"]]
        if not sub:
            continue
        lines.append(f"| {label} | {sum(s['n'] for s in sub)} | "
                     f"{statistics.fmean([s['gross'] for s in sub]):+.1f} | "
                     f"{statistics.fmean([s['t'] for s in sub if s['t'] is not None] or [float('nan')]):+.2f} |")
    lines.append("")

    lines.append("## 4. 判定")
    lines.append("")
    excess = _avg("excess")
    net = _avg("net")
    if excess - args.cost > 0 and positives >= max(3, int(0.6 * len(results))):
        lines.append(f"**候选成立(初筛)**:超额 {excess:+.1f} bps、净 {net:+.1f} bps、"
                     f"{positives}/{len(results)} 品种同号 → 进 G1′(有效片段 ≥2,000)与长历史 walk-forward。")
    else:
        lines.append(f"**候选不成立**:超额 {excess:+.1f} bps、净 {net:+.1f} bps、"
                     f"{positives}/{len(results)} 品种同号 → 达不到 G1′。")
    lines.append("")
    lines.append("> 注意:分年份是**事后**切分,只用于判断 regime 依赖,不能据此挑选年份。")
    lines.append("")

    out_dir = REPORT_ROOT / args.date
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = f"candidate-{args.rule}-h{args.horizon}"
    (out_dir / f"{slug}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / f"{slug}.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print(f"[written] {out_dir / (slug + '.md')}")


if __name__ == "__main__":
    main()
