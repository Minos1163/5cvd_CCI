"""把 long/flat 当"持仓的降回撤叠加"来测:买入持有 vs 趋势过滤(现货口径)。

背景
----
前面几轮已经确认:
- 15m 评分体系没有毛边际;
- 4h long/flat 趋势规则在**时点池**的老山寨上没有绝对收益(full −1.4%、中位 −42.4%);
- 但它唯一还站得住的性质是**回撤更低**(检验窗口 33% vs BTC 53%)。

所以现在要问的是一个不同的问题:**把这条规则套在"本来就长期上涨"的载体上(BTC/ETH),
它能不能做到"收益不差、回撤明显更低"?**

口径
----
- **现货口径**:持有现货,趋势向下时换成现金(稳定币);不涉及永续资金费,也不做空;
- 数据:4h K 线,`t` 收盘定状态,`t+1` 开盘换仓;
- 换手成本:每次状态变化 **20bps 往返**(现货双边手续费+滑点的保守估计);
- 空仓期收益 = 0(不计稳定币利息);
- 检查频率:每 `horizon` 根检查一次,主结果用 42 根(7 天),另给 6/24/60 根做敏感性;
- 指标:CAGR、最大回撤、Calmar、在场时间占比、换手次数、逐年收益。

判定(事先写死)
----------------
叠加"有用"需要同时满足:
1. CAGR 不低于买入持有的 90%;
2. 最大回撤 ≤ 买入持有的 75%;
3. 逐年最差一年不比买入持有更差超过 5 个百分点。

用法
----
    python scripts/analysis/btc_overlay_20261020.py
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


def prepare(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("ts").reset_index(drop=True)
    close = df["close"]
    df["sma50"] = close.rolling(50).mean()
    df["sma200"] = close.rolling(200).mean()
    df["up"] = (df["sma50"] > df["sma200"]).astype(int)
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df["year"] = df["dt"].dt.year
    return df


def simulate(df: pd.DataFrame, horizon: int, cost_bps: float, *, overlay: bool) -> dict:
    pos = 0
    switches = 0
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    in_market = 0
    bars = 0
    yearly: dict[int, float] = {}
    year_start_equity = 1.0
    current_year = int(df.at[0, "year"])
    i = 0
    while i + 2 < len(df):
        year = int(df.at[i + 1, "year"])
        if year != current_year:
            yearly[current_year] = equity / year_start_equity - 1
            year_start_equity = equity
            current_year = year
        if overlay and (i % horizon) == 0:
            target = int(df.at[i, "up"])
            if target != pos:
                switches += 1
                equity *= (1.0 - cost_bps / 1e4)
                pos = target
        if not overlay:
            pos = 1
        gross = float(df.at[i + 2, "open"]) / float(df.at[i + 1, "open"]) - 1.0
        equity *= (1.0 + pos * gross)
        peak = max(peak, equity)
        mdd = max(mdd, (peak - equity) / peak)
        in_market += pos
        bars += 1
        i += 1
    yearly[current_year] = equity / year_start_equity - 1
    years = bars * BAR_HOURS / 24 / 365
    cagr = equity ** (1 / years) - 1 if years > 0 and equity > 0 else float("nan")
    return {"cagr": cagr, "max_dd": mdd, "calmar": (cagr / mdd) if mdd > 0 else float("nan"),
            "equity": equity, "switches": switches, "years": years,
            "in_market_pct": in_market / bars if bars else 0.0, "yearly": yearly}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    ap.add_argument("--horizons", default="6,24,42,60")
    ap.add_argument("--cost", type=float, default=20.0)
    ap.add_argument("--date", default="2026-10-20")
    args = ap.parse_args()

    horizons = [int(x) for x in args.horizons.split(",")]
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    results: dict[str, dict] = {}

    for symbol in symbols:
        path = CACHE / f"{symbol}_{INTERVAL}.csv"
        if not path.exists():
            print(f"[skip] {symbol}: no cache")
            continue
        df = prepare(path)
        if len(df) < 1000:
            print(f"[skip] {symbol}: too few bars")
            continue
        entry = {"buy_hold": simulate(df, 42, args.cost, overlay=False)}
        for horizon in horizons:
            entry[f"overlay_h{horizon}"] = simulate(df, horizon, args.cost, overlay=True)
        results[symbol] = entry

    if not results:
        raise SystemExit("no data")

    lines = ["# 降回撤叠加检验:BTC/ETH 买入持有 vs 趋势过滤(现货口径)", "",
             f"- 成本:每次换手 {args.cost:.0f}bps 往返;空仓期收益计 0(不含稳定币利息)",
             "- 主结果 = 42 根(7 天)检查;6/24/60 根仅作敏感性", ""]

    for symbol, entry in results.items():
        bh = entry["buy_hold"]
        lines.append(f"## {symbol}")
        lines.append("")
        lines.append("| 配置 | 年化 | 最大回撤 | Calmar | 在场时间 | 换手 |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        lines.append(f"| 买入持有 | {bh['cagr']:+.1%} | {bh['max_dd']:.0%} | {bh['calmar']:.2f} | 100% | 0 |")
        for key in sorted(k for k in entry if k.startswith("overlay_h")):
            item = entry[key]
            lines.append(f"| {key.replace('overlay_h', '趋势过滤 h=')} | {item['cagr']:+.1%} | "
                         f"{item['max_dd']:.0%} | {item['calmar']:.2f} | "
                         f"{item['in_market_pct']:.0%} | {item['switches']} |")
        lines.append("")

        # 逐年对比(主口径 42 根)
        main = entry["overlay_h42"]
        years = sorted(set(bh["yearly"]) | set(main["yearly"]))
        lines.append("| 年份 | 买入持有 | 趋势过滤(h=42) | 差 |")
        lines.append("|---|---:|---:|---:|")
        for year in years:
            a = bh["yearly"].get(year, float("nan"))
            b = main["yearly"].get(year, float("nan"))
            lines.append(f"| {year} | {a:+.1%} | {b:+.1%} | {b - a:+.1%} |")
        lines.append("")

        # 判定
        cagr_ok = main["cagr"] >= bh["cagr"] * 0.9
        dd_strict = main["max_dd"] <= bh["max_dd"] * 0.75
        dd_looser = main["max_dd"] < bh["max_dd"]
        worst_bh = min(bh["yearly"].values())
        worst_of = min(main["yearly"].values())
        worst_ok = worst_of >= worst_bh - 0.05
        lines.append(f"- 判定:CAGR {main['cagr']:+.1%} vs {bh['cagr']:+.1%}"
                     f"({'通过' if cagr_ok else '**不通过**'});"
                     f"回撤 {main['max_dd']:.0%} vs {bh['max_dd']:.0%}"
                     f"(更低:{'是' if dd_looser else '否'} / 严格≤75%:{'是' if dd_strict else '否'});"
                     f"最差年 {worst_of:+.1%} vs {worst_bh:+.1%} "
                     f"({'通过' if worst_ok else '**不通过**'})")
        if cagr_ok and dd_strict and worst_ok:
            lines.append(f"- **{symbol}:叠加成立(严格口径)** —— 收益保住,回撤 {bh['max_dd']:.0%} → "
                         f"{main['max_dd']:.0%},Calmar {bh['calmar']:.2f} → {main['calmar']:.2f}。")
        elif cagr_ok and dd_looser and worst_ok:
            lines.append(f"- **{symbol}:方向性改善,但回撤未压到 75% 以内**"
                         f"({main['max_dd']:.0%} vs {bh['max_dd']:.0%});"
                         f"Calmar {bh['calmar']:.2f} → {main['calmar']:.2f}。")
        else:
            lines.append(f"- **{symbol}:叠加不成立**(至少一条不通过)。")
        lines.append("")

    lines.append("> 说明:这是**现货口径**,不含永续资金费(买现货本来就不付资金费);"
                 "若将来在永续上实现同一规则,需再扣资金费(前一轮实测 −3.6%~+7.1%/年,随 regime 变)。")
    lines.append("")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / args.date).mkdir(parents=True, exist_ok=True)
    slug = "btc-eth-overlay"
    (OUT / args.date / f"{slug}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / args.date / f"{slug}.json").write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    print("\n".join(lines))
    print(f"[written] {OUT / args.date / (slug + '.md')}")


if __name__ == "__main__":
    main()
