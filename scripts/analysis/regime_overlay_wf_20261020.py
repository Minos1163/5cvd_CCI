"""预登记网格 + walk-forward:决定 `regime_overlay` 用哪组参数。

预登记(跑之前写死,不许回头改)
--------------------------------
- 网格:MA ∈ {(20,100), (50,200)} × 检查频率 h ∈ {24, 42} 根(4h)= 4 个候选;
- 标的:**BTC / ETH / BNB**(上一轮严格过门的三个);
- 训练窗口 2021-10-21 ~ 2024-12-31;检验窗口 2025-01-01 ~ 2026-10-20;
- **参数只在训练窗口上选**:选"三个标的平均 Calmar 最高、且每只在训练窗口回撤低于买入持有"的那组;
- 选定后**只在检验窗口跑一次**,不再改参数;
- 检验判定(与上一轮一致):每只标的 ①CAGR ≥ 买入持有 ×90% ②最大回撤 ≤ 买入持有 ×75%;
  三只里 **≥2 只同时满足**算通过。

口径:现货、20bps/次换手、空仓收益计 0(不含稳定币利息)。

产出:`logs/analysis/long-history/2026-10-20/regime-overlay-wf.md` 与 `.json`
"""

from __future__ import annotations

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
TRAIN_END = "2024-12-31"
TEST_START = "2025-01-01"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
GRID = [(20, 100, 42), (20, 100, 24), (50, 200, 42), (50, 200, 24)]
COST_BPS = 20.0


def prepare(symbol: str, fast: int, slow: int) -> pd.DataFrame:
    df = pd.read_csv(CACHE / f"{symbol}_{INTERVAL}.csv")
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("ts").reset_index(drop=True)
    close = df["close"]
    df["ma_fast"] = close.rolling(fast).mean()
    df["ma_slow"] = close.rolling(slow).mean()
    df["up"] = (df["ma_fast"] > df["ma_slow"]).astype(int)
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df


def simulate(df: pd.DataFrame, horizon: int, *, overlay: bool) -> dict:
    pos = 0
    switches = 0
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    bars = 0
    i = 0
    while i + 2 < len(df):
        if overlay and (i % horizon) == 0:
            target = int(df.at[i, "up"])
            if target != pos:
                switches += 1
                equity *= (1.0 - COST_BPS / 1e4)
                pos = target
        if not overlay:
            pos = 1
        gross = float(df.at[i + 2, "open"]) / float(df.at[i + 1, "open"]) - 1.0
        equity *= (1.0 + pos * gross)
        peak = max(peak, equity)
        mdd = max(mdd, (peak - equity) / peak)
        bars += 1
        i += 1
    years = bars * BAR_HOURS / 24 / 365
    cagr = equity ** (1 / years) - 1 if years > 0 and equity > 0 else float("nan")
    return {"cagr": cagr, "max_dd": mdd, "calmar": (cagr / mdd) if mdd > 0 else float("nan"),
            "switches": switches, "years": years}


def window(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    sub = df
    if start:
        sub = sub[sub["dt"] >= pd.Timestamp(start, tz="UTC")]
    if end:
        sub = sub[sub["dt"] <= pd.Timestamp(end, tz="UTC")]
    return sub.reset_index(drop=True)


def main() -> None:
    rows = []
    # ---------- 训练窗口:选参数 ----------
    for fast, slow, horizon in GRID:
        per_symbol = {}
        for symbol in SYMBOLS:
            df = prepare(symbol, fast, slow)
            train = window(df, None, TRAIN_END)
            if len(train) < 500:
                continue
            bh = simulate(train, horizon, overlay=False)
            ov = simulate(train, horizon, overlay=True)
            per_symbol[symbol] = {"bh": bh, "overlay": ov}
        if len(per_symbol) < 2:
            continue
        mean_calmar = statistics.fmean([v["overlay"]["calmar"] for v in per_symbol.values()])
        dd_ok_all = all(v["overlay"]["max_dd"] < v["bh"]["max_dd"] for v in per_symbol.values())
        rows.append({"fast": fast, "slow": slow, "horizon": horizon,
                     "mean_train_calmar": mean_calmar, "dd_ok_all": dd_ok_all,
                     "per_symbol": {k: {"bh_cagr": v["bh"]["cagr"], "bh_dd": v["bh"]["max_dd"],
                                        "ov_cagr": v["overlay"]["cagr"], "ov_dd": v["overlay"]["max_dd"],
                                        "ov_calmar": v["overlay"]["calmar"]}
                                    for k, v in per_symbol.items()}})

    eligible = [r for r in rows if r["dd_ok_all"]]
    pool = eligible or rows
    chosen = max(pool, key=lambda r: r["mean_train_calmar"])

    # ---------- 检验窗口:只跑选中的这一组 ----------
    test_rows = {}
    for symbol in SYMBOLS:
        df = prepare(symbol, chosen["fast"], chosen["slow"])
        test = window(df, TEST_START, None)
        if len(test) < 500:
            continue
        bh = simulate(test, chosen["horizon"], overlay=False)
        ov = simulate(test, chosen["horizon"], overlay=True)
        pass_cagr = ov["cagr"] >= bh["cagr"] * 0.9
        pass_dd = ov["max_dd"] <= bh["max_dd"] * 0.75
        test_rows[symbol] = {"bh": bh, "overlay": ov,
                             "pass_cagr": pass_cagr, "pass_dd": pass_dd,
                             "pass": pass_cagr and pass_dd}

    passed = sum(1 for v in test_rows.values() if v["pass"])
    verdict = "PASS" if passed >= 2 else "FAIL"

    lines = ["# regime_overlay:预登记网格 + walk-forward", "",
             f"- 网格:MA(20/100) 与 (50/200) × h∈{{24,42}};标的 {', '.join(SYMBOLS)}",
             f"- 训练 2021-10-21~{TRAIN_END},检验 {TEST_START}~2026-10-20(只跑一次)",
             f"- 成本 {COST_BPS:.0f}bps/次换手;现货口径,空仓收益计 0", "",
             "## 1. 训练窗口:4 组候选", "",
             "| MA | h | 平均 Calmar | 回撤均低于买入持有 | BTC 年化/DD | ETH 年化/DD | BNB 年化/DD |",
             "|---|---:|---:|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: -x["mean_train_calmar"]):
        cells = []
        for symbol in SYMBOLS:
            item = r["per_symbol"].get(symbol)
            cells.append(f"{item['ov_cagr']:+.1%}/{item['ov_dd']:.0%}" if item else "-")
        mark = " ← 选中" if r is chosen else ""
        lines.append(f"| {r['fast']}/{r['slow']} | {r['horizon']} | {r['mean_train_calmar']:.2f} | "
                     f"{'是' if r['dd_ok_all'] else '否'} | {cells[0]} | {cells[1]} | {cells[2]}{mark} |")
    lines.append("")
    lines.append(f"**选中参数:MA({chosen['fast']}/{chosen['slow']}),h={chosen['horizon']}**"
                 f"(训练口径平均 Calmar {chosen['mean_train_calmar']:.2f})")
    lines.append("")
    lines.append("## 2. 检验窗口(只跑一次)")
    lines.append("")
    lines.append("| 品种 | 买入持有 年化/DD | 叠加 年化/DD | Calmar(BH→叠加) | 收益门 | 回撤门 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    for symbol, item in test_rows.items():
        bh, ov = item["bh"], item["overlay"]
        lines.append(f"| {symbol} | {bh['cagr']:+.1%} / {bh['max_dd']:.0%} | {ov['cagr']:+.1%} / {ov['max_dd']:.0%} | "
                     f"{bh['calmar']:.2f} → {ov['calmar']:.2f} | "
                     f"{'过' if item['pass_cagr'] else '**不过**'} | "
                     f"{'过' if item['pass_dd'] else '**不过**'} | "
                     f"{'**过门**' if item['pass'] else '不过门'} |")
    lines.append("")
    lines.append(f"## 3. 结论:**{verdict}**({passed}/{len(test_rows)} 只同时满足两条)")
    lines.append("")
    if verdict == "PASS":
        lines.append("→ 参数在训练窗口选出、检验窗口一次通过,允许实现 `regime_overlay`"
                     "(默认 off,先 shadow)。")
    else:
        lines.append("→ 不实现 `regime_overlay`;保留分析脚本,结论归档为负。")
    lines.append("")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "2026-10-20").mkdir(parents=True, exist_ok=True)
    (OUT / "2026-10-20" / "regime-overlay-wf.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "2026-10-20" / "regime-overlay-wf.json").write_text(json.dumps(
        {"grid": rows, "chosen": {k: chosen[k] for k in ("fast", "slow", "horizon")},
         "test": {k: {"bh": v["bh"], "overlay": v["overlay"], "pass": v["pass"]}
                  for k, v in test_rows.items()}, "verdict": verdict},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print(f"[written] {OUT / '2026-10-20' / 'regime-overlay-wf.md'}")


if __name__ == "__main__":
    main()
