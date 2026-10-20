"""长周期"趋势过滤 + 长/空仓"与买入持有的对比(4h,5 年)。

为什么要单独算这个
------------------
`long_history_probe` 测的是 ±1 持仓的**均值 bps**,结果被 beta 主导:
sma50_200 在 7 天持有期上毛 +171bps、基准(永远做多)+120bps、超额 +51bps,
但空头腿几乎为 0(t=0.04)——也就是说这套规则赚的是"牛市里在场"的钱。

对实际部署来说,更有意义的问题不是"能不能预测",而是:
**用趋势过滤把"永远在场"换成"趋势向上才在场",收益和回撤会怎样?**
这是"少亏"的问题,不是"多赚"的问题,必须用 CAGR / 最大回撤 / Calmar 衡量,
而不是均值 bps。

口径
----
- 4h bar,`t` 收盘定状态,`t+1` 开盘换仓;每 `horizon` 根检查一次;
- 三种模式:`buy_hold`(永远满仓)、`long_flat`(趋势向上满仓,否则空仓)、
  `long_short`(趋势向上做多、向下做空);
- 每次状态变化扣 `cost_bps` 往返;
- 等权组合:每个品种独立跑,再等权再平衡(近似:收益取等权平均)。

用法
----
    python scripts/analysis/long_flat_overlay_20261020.py --rule sma50_200 --horizon 42
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
OUT = ROOT / "logs" / "analysis" / "long-history"
INTERVAL = "4h"
BAR_HOURS = 4
BARS_PER_YEAR = 365 * 24 / BAR_HOURS


def prepare(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("ts").reset_index(drop=True)
    close = df["close"]
    df["sma50"] = close.rolling(50).mean()
    df["sma200"] = close.rolling(200).mean()
    df["ema200"] = close.ewm(span=200, adjust=False).mean()
    df["date"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.strftime("%Y-%m-%d")
    df["up_sma50_200"] = (df["sma50"] > df["sma200"]).astype(int)
    df["up_ema200"] = (close > df["ema200"]).astype(int)
    return df


def simulate(df: pd.DataFrame, upcol: str, horizon: int, cost_bps: float,
             mode: str) -> dict:
    """返回年化收益、最大回撤、Calmar、换手次数。"""
    n = len(df)
    equity = 1.0
    curve = [1.0]
    peak = 1.0
    max_dd = 0.0
    switches = 0
    pos = 0
    i = 200  # 前 200 根留给均线
    bars_held = 0
    while i + horizon + 1 < n:
        if bars_held % horizon == 0:
            up = int(df.at[i, upcol])
            target = 1 if mode == "buy_hold" else (up if mode == "long_flat" else (1 if up else -1))
            if target != pos:
                switches += 1
                equity *= (1.0 - cost_bps / 1e4)
                pos = target
        entry = float(df.at[i + 1, "open"])
        exit_ = float(df.at[i + 2, "open"])
        if entry > 0 and pos != 0:
            equity *= (1.0 + pos * (exit_ / entry - 1.0))
        curve.append(equity)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
        i += 1
        bars_held += 1
    years = (n - 200) * BAR_HOURS / 24 / 365
    cagr = equity ** (1 / years) - 1 if years > 0 and equity > 0 else float("nan")
    return {"equity": equity, "cagr": cagr, "max_dd": max_dd,
            "calmar": (cagr / max_dd) if max_dd > 0 else float("nan"),
            "switches": switches, "years": years}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", default="sma50_200", choices=["sma50_200", "ema200"])
    ap.add_argument("--horizon", type=int, default=42)
    ap.add_argument("--cost", type=float, default=20.0)
    ap.add_argument("--date", default="2026-10-20")
    args = ap.parse_args()

    upcol = "up_sma50_200" if args.rule == "sma50_200" else "up_ema200"
    rows = []
    for path in sorted(CACHE.glob(f"*_{INTERVAL}.csv")):
        symbol = path.stem.split("_")[0]
        df = prepare(path)
        if len(df) < 1000:
            continue
        item = {"symbol": symbol, "bars": len(df)}
        for mode in ("buy_hold", "long_flat", "long_short"):
            res = simulate(df, upcol, args.horizon, args.cost, mode)
            item[mode] = res
        rows.append(item)
    if not rows:
        raise SystemExit("no data")

    def _avg(mode: str, key: str) -> float:
        vals = [r[mode][key] for r in rows if not math.isnan(r[mode][key])]
        return statistics.fmean(vals) if vals else float("nan")

    def _med(mode: str, key: str) -> float:
        vals = [r[mode][key] for r in rows if not math.isnan(r[mode][key])]
        return statistics.median(vals) if vals else float("nan")

    lines = [f"# 趋势过滤 vs 买入持有(4h,5 年):{args.rule} / 每 {args.horizon} 根检查", "",
             f"- 成本:每次状态变化 {args.cost:.0f}bps 往返", f"- 品种数:{len(rows)}", "",
             "> **均值会被个别暴涨品种主导**(例如新上市的 LAB),所以同时给中位数;"
             "判断应以中位数为准,均值为参考。", "",
             "## 1. 跨品种(均值 / 中位数)", "",
             "| 模式 | 年化(均) | 年化(中位) | 最大回撤(中位) | Calmar(中位) | 换手次数 |",
             "|---|---:|---:|---:|---:|---:|"]
    for mode, label in (("buy_hold", "买入持有"), ("long_flat", "趋势多/空仓"), ("long_short", "趋势多空")):
        lines.append(f"| {label} | {_avg(mode,'cagr'):+.1%} | **{_med(mode,'cagr'):+.1%}** | "
                     f"{_med(mode,'max_dd'):.0%} | {_med(mode,'calmar'):.2f} | "
                     f"{_avg(mode,'switches'):.0f} |")
    lines.append("")

    lines.append("## 2. 分品种(年化 / 最大回撤)")
    lines.append("")
    lines.append("| 品种 | 买入持有 | 趋势多/空仓 | 多空 |")
    lines.append("|---|---:|---:|---:|")
    for r in rows:
        lines.append(f"| {r['symbol']} | {r['buy_hold']['cagr']:+.1%} / {r['buy_hold']['max_dd']:.0%} | "
                     f"{r['long_flat']['cagr']:+.1%} / {r['long_flat']['max_dd']:.0%} | "
                     f"{r['long_short']['cagr']:+.1%} / {r['long_short']['max_dd']:.0%} |")
    lines.append("")

    bh_cagr, bh_dd = _med("buy_hold", "cagr"), _med("buy_hold", "max_dd")
    lf_cagr, lf_dd = _med("long_flat", "cagr"), _med("long_flat", "max_dd")
    ls_cagr, ls_dd = _med("long_short", "cagr"), _med("long_short", "max_dd")
    lines.append("## 3. 判定(以中位数为准)")
    lines.append("")
    lines.append(f"- 买入持有:年化中位 {bh_cagr:+.1%}、回撤中位 {bh_dd:.0%}")
    lines.append(f"- 趋势多/空仓:年化中位 {lf_cagr:+.1%}、回撤中位 {lf_dd:.0%}")
    lines.append(f"- 趋势多空:年化中位 {ls_cagr:+.1%}、回撤中位 {ls_dd:.0%}")
    lines.append("")
    if lf_dd < bh_dd * 0.8 and lf_cagr >= bh_cagr * 0.8:
        lines.append(f"**趋势过滤有价值(以回撤论)**:回撤中位 {lf_dd:.0%} vs {bh_dd:.0%}"
                     f"(−{(1-lf_dd/bh_dd):.0%}),年化中位 {lf_cagr:+.1%} vs {bh_cagr:+.1%}。")
        lines.append("")
        lines.append("→ 它的定位应是**风险预算工具**(降回撤、抬 Calmar),"
                     "而不是\"预测入场\"的 alpha;可作为 S1 的第一版部署形态。")
    elif lf_cagr < bh_cagr and lf_dd >= bh_dd * 0.8:
        lines.append("**趋势过滤没有价值**:收益不如买入持有,回撤也没降下来。")
    else:
        lines.append("**结论不明确**:收益与回撤一好一坏,需要看逐年与样本外。")
    lines.append("")
    lines.append("> 说明:等权平均是跨品种年化的算术平均,不等于组合收益;"
                 "未计资金费(4h 持仓跨结算期,实际成本更高);未做样本外切分。")
    lines.append("")

    OUT.mkdir(parents=True, exist_ok=True)
    slug = f"overlay-{args.rule}-h{args.horizon}"
    (OUT / args.date).mkdir(parents=True, exist_ok=True)
    (OUT / args.date / f"{slug}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / args.date / f"{slug}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print(f"[written] {OUT / args.date / (slug + '.md')}")


if __name__ == "__main__":
    main()
