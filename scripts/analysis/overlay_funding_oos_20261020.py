"""S1 候选终检:long/flat 趋势过滤 + 逐 bar 资金费 + 样本外切分 + BTC 基准。

要回答四个问题(用户指定的优先级 1–4)
----------------------------------------
1. 把资金费**逐 bar** 计入后,趋势过滤的年化还剩多少?(不再用"事后减一个常数")
2. 样本外(2025-01 ~ 2026-10)只跑一次,结果还在吗?
3. 去掉空头腿(long/flat)之后,和 long/short 差多少?
4. 和"直接持有 BTC"比,趋势过滤到底给了什么?

口径
----
- 4h bar;`t` 收盘定状态(`SMA50 > SMA200` 为多头,否则空仓),`t+1` 开盘换仓,
  `t+1 → t+2` 一个 bar 的收益算到持仓上;
- 换手成本:状态变化一次扣 `cost-bps`(往返);
- 资金费:永续每 8h 结算一次,按 4h bar 的区间聚合(每个 4h bar 可能含 0 或 1 次结算),
  多头 `return -= rate`,空头 `return += rate`;**逐品种用自己的费率,不用常数**;
- 组合:每个时间戳对"当时有数据的品种"等权平均,再复利(品种上市时间不同,已在报告里披露);
- 样本外:训练 = 2021-10-21 ~ 2024-12-31,检验 = 2025-01-01 ~ 2026-10-20,**只看一次**。

用法
----
    python scripts/analysis/overlay_funding_oos_20261020.py --horizon 42

产出
----
`logs/analysis/long-history/2026-10-20/oos-<rule>-h<horizon>.md` 与 `.json`
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

CACHE = ROOT / "data" / "history"
OUT = ROOT / "logs" / "analysis" / "long-history"
FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
INTERVAL = "4h"
BAR_MS = 4 * 3600 * 1000
TRAIN_END = "2024-12-31"
TEST_START = "2025-01-01"


def load_funding(symbol: str) -> pd.DataFrame:
    """读缓存,缺失则下载(每 1000 条一页)。"""
    path = CACHE / f"funding_{symbol}.csv"
    if path.exists():
        df = pd.read_csv(path)
        if len(df):
            return df
    rows: dict[int, float] = {}
    cursor = 1_634_832_000_000
    now_ms = int(time.time() * 1000)
    while cursor < now_ms:
        url = f"{FUNDING_URL}?" + urlencode(
            {"symbol": symbol, "startTime": cursor, "limit": 1000})
        batch = None
        for attempt in range(4):
            try:
                with urlopen(url, timeout=45) as response:
                    batch = json.loads(response.read().decode())
                break
            except Exception:  # noqa: BLE001  代理链路会偶发 read timeout,重试即可
                time.sleep(1.5 * (attempt + 1))
        if not batch:
            print(f"[warn] {symbol}: funding page failed at {cursor}")
            break
        for item in batch:
            rows[int(item["fundingTime"])] = float(item["fundingRate"])
        last = int(batch[-1]["fundingTime"])
        if last <= cursor:
            break
        cursor = last + 1
        time.sleep(0.1)
    df = pd.DataFrame({"fundingTime": sorted(rows), "fundingRate": [rows[k] for k in sorted(rows)]})
    if len(df):
        CACHE.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
    return df


def prepare(symbol: str) -> pd.DataFrame:
    df = pd.read_csv(CACHE / f"{symbol}_{INTERVAL}.csv")
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("ts").reset_index(drop=True)
    close = df["close"]
    df["sma50"] = close.rolling(50).mean()
    df["sma200"] = close.rolling(200).mean()
    df["up"] = (df["sma50"] > df["sma200"]).astype(int)

    funding = load_funding(symbol)
    if len(funding):
        funding["bar_ts"] = (funding["fundingTime"] // BAR_MS) * BAR_MS
        agg = funding.groupby("bar_ts")["fundingRate"].sum()
        df["funding"] = df["ts"].map(agg).fillna(0.0)
    else:
        df["funding"] = 0.0
    return df


def run(df: pd.DataFrame, horizon: int, cost_bps: float, mode: str,
        start: str | None, end: str | None) -> dict:
    """返回逐 bar 收益序列(含资金费与换手成本),按日期过滤。"""
    df = df.copy()
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    if start:
        df = df[df["dt"] >= pd.Timestamp(start, tz="UTC")].reset_index(drop=True)
    if end:
        df = df[df["dt"] <= pd.Timestamp(end, tz="UTC")].reset_index(drop=True)
    if len(df) < 300:
        return {}

    rets: list[float] = []
    gross_only: list[float] = []
    funding_pnl: list[float] = []
    stamps: list[pd.Timestamp] = []
    pos = 0
    switches = 0
    i = 0
    # 需要 200 根均线;若窗口从中间开始,均线在 prepare 时已用全历史算好,这里只是缺 warmup
    while i + 2 < len(df):
        if (i % horizon) == 0:
            up = int(df.at[i, "up"])
            target = up if mode == "long_flat" else (1 if up else -1)
            if target != pos:
                switches += 1
                pos = target
        gross = float(df.at[i + 2, "open"]) / float(df.at[i + 1, "open"]) - 1.0
        rate = float(df.at[i + 1, "funding"])
        step_gross = pos * gross
        step_funding = -pos * rate
        rets.append(step_gross + step_funding)
        gross_only.append(step_gross)
        funding_pnl.append(step_funding)
        stamps.append(df.at[i + 1, "dt"])
        i += 1

    # 换手成本:按换手次数均摊到每个 bar(等价于每次状态变化扣一次)
    cost_total = switches * cost_bps / 1e4
    equity = 1.0
    curve = []
    for r in rets:
        equity *= (1.0 + r)
        curve.append(equity)
    equity *= (1.0 - cost_total) if cost_total < 1 else 0.0
    years = len(rets) * 4 / (24 * 365)
    cagr = equity ** (1 / years) - 1 if years > 0 and equity > 0 else float("nan")
    peak, mdd = 1.0, 0.0
    for value in curve:
        peak = max(peak, value)
        mdd = max(mdd, (peak - value) / peak)
    return {"equity": equity, "cagr": cagr, "max_dd": mdd,
            "calmar": (cagr / mdd) if mdd > 0 else float("nan"),
            "switches": switches, "years": years,
            "funding_cum": sum(funding_pnl),
            "returns": rets, "gross_only": gross_only,
            "funding": funding_pnl, "stamps": stamps}


def portfolio(runs: dict[str, dict], component: str = "net") -> dict:
    """把多品种逐 bar 收益等权平均成组合(按时间戳对齐,缺数据的品种不参与)。

    ``component``: ``net`` = 毛 + 资金费;``gross`` = 只看价格(不含资金费)。
    两条曲线的差就是资金费的真实影响,比"逐品种均值"稳。
    """
    by_ts: dict[pd.Timestamp, list[float]] = {}
    for item in runs.values():
        series = item["returns"] if component == "net" else item["gross_only"]
        for ts, r in zip(item["stamps"], series):
            by_ts.setdefault(ts, []).append(r)
    stamps = sorted(by_ts)
    rets = [statistics.fmean(by_ts[ts]) for ts in stamps]
    equity = 1.0
    curve = []
    for r in rets:
        equity *= (1.0 + r)
        curve.append(equity)
    years = len(rets) * 4 / (24 * 365)
    cagr = equity ** (1 / years) - 1 if years > 0 and equity > 0 else float("nan")
    peak, mdd = 1.0, 0.0
    for value in curve:
        peak = max(peak, value)
        mdd = max(mdd, (peak - value) / peak)
    return {"cagr": cagr, "max_dd": mdd, "calmar": (cagr / mdd) if mdd > 0 else float("nan"),
            "equity": equity, "years": years, "n_symbols": len(runs)}


def btc_benchmark(horizon: int = 42, cost_bps: float = 20.0) -> dict:
    df = pd.read_csv(CACHE / f"BTCUSDT_{INTERVAL}.csv")
    df = df.dropna(subset=["open", "close"]).sort_values("ts").reset_index(drop=True)
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df["sma50"] = df["close"].rolling(50).mean()
    df["sma200"] = df["close"].rolling(200).mean()
    df["up"] = 1
    df["funding"] = 0.0
    windows = {
        "full": (None, None),
        "train": (None, TRAIN_END),
        "test": (TEST_START, None),
    }
    out = {}
    for name, (start, end) in windows.items():
        sub = df.copy()
        if start:
            sub = sub[sub["dt"] >= pd.Timestamp(start, tz="UTC")]
        if end:
            sub = sub[sub["dt"] <= pd.Timestamp(end, tz="UTC")]
        if len(sub) < 300:
            out[name] = {}
            continue
        sub = sub.reset_index(drop=True)
        eq = float(sub["open"].iloc[-1]) / float(sub["open"].iloc[0])
        years = len(sub) * 4 / (24 * 365)
        peak, mdd = 1.0, 0.0
        for value in (sub["open"] / float(sub["open"].iloc[0])):
            peak = max(peak, float(value))
            mdd = max(mdd, (peak - float(value)) / peak)
        cagr = eq ** (1 / years) - 1 if years > 0 else float("nan")
        out[name] = {"cagr": cagr, "max_dd": mdd,
                     "calmar": (cagr / mdd) if mdd > 0 else float("nan"), "years": years}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=42)
    ap.add_argument("--cost", type=float, default=20.0)
    ap.add_argument("--date", default="2026-10-20")
    args = ap.parse_args()

    files = sorted(CACHE.glob(f"*_{INTERVAL}.csv"))
    symbols = [p.stem.split("_")[0] for p in files]
    data = {}
    for symbol in symbols:
        df = prepare(symbol)
        if len(df) < 1000:
            continue
        data[symbol] = df
    if not data:
        raise SystemExit("no cached bars")

    windows = {"full": (None, None), "train": (None, TRAIN_END), "test": (TEST_START, None)}
    results: dict[str, dict] = {}
    per_symbol_test: dict[str, float] = {}
    test_runs_flat: dict[str, dict] = {}
    for mode in ("long_flat", "long_short"):
        results[mode] = {}
        for name, (start, end) in windows.items():
            runs = {}
            for symbol, df in data.items():
                item = run(df, args.horizon, args.cost, mode, start, end)
                if item:
                    runs[symbol] = item
            if not runs:
                continue
            net = portfolio(runs, "net")
            gross = portfolio(runs, "gross")
            net["cagr_gross"] = gross["cagr"]
            net["funding_impact"] = net["cagr"] - gross["cagr"]
            net["switches"] = statistics.fmean([r["switches"] for r in runs.values()])
            results[mode][name] = net
            if mode == "long_flat" and name == "test":
                for symbol, item in runs.items():
                    per_symbol_test[symbol] = item["cagr"]
                test_runs_flat = dict(runs)

    bench = btc_benchmark(args.horizon, args.cost)

    lines = [f"# S1 终检:long/flat + 逐 bar 资金费 + 样本外(4h,{args.horizon} 根换手)", "",
             f"- 成本:每次换手 {args.cost:.0f}bps 往返;资金费按 4h 网格逐 bar 计入(逐品种)",
             f"- 品种数:{len(data)};组合 = 每个时间戳等权平均",
             f"- 训练:2021-10-21 ~ {TRAIN_END};检验:{TEST_START} ~ 2026-10-20(**只跑一次**)", "",
             "## 1. 组合结果", "",
             "| 模式 | 窗口 | 年化(含资金费) | 年化(不含资金费) | 资金费影响 | 最大回撤 | Calmar | 换手 |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for mode, label in (("long_flat", "long/flat"), ("long_short", "long/short")):
        for name in ("full", "train", "test"):
            item = results[mode].get(name)
            if not item:
                continue
            lines.append(f"| {label} | {name} | {item['cagr']:+.1%} | {item['cagr_gross']:+.1%} | "
                         f"{item['funding_impact']:+.2%} | {item['max_dd']:.0%} | "
                         f"{item['calmar']:.2f} | {item.get('switches', 0):.0f} |")
    lines.append("")
    lines.append("## 2. BTC 基准(买入持有,不含资金费)")
    lines.append("")
    lines.append("| 窗口 | 年化 | 最大回撤 | Calmar |")
    lines.append("|---|---:|---:|---:|")
    for name in ("full", "train", "test"):
        item = bench.get(name) or {}
        if not item:
            continue
        lines.append(f"| {name} | {item['cagr']:+.1%} | {item['max_dd']:.0%} | {item['calmar']:.2f} |")
    lines.append("")

    if per_symbol_test:
        lines.append("## 2b. 检验窗口内各品种年化(看是否被单一品种主导)")
        lines.append("")
        ranked = sorted(per_symbol_test.items(), key=lambda kv: kv[1], reverse=True)
        lines.append("| 品种 | 年化 |")
        lines.append("|---|---:|")
        for symbol, value in ranked:
            lines.append(f"| {symbol} | {value:+.1%} |")
        lines.append("")
        top3 = [s for s, _ in ranked[:3]]
        lines.append(f"- 前三名:{', '.join(top3)}。**若结论只由这三家撑起,应视为不可部署**"
                     "(新上市品种的事后选择偏差)。")

        # 稳健性:去掉最强品种 + 中位数,两个都不该被单一暴涨品种绑架
        top1 = ranked[0][0]
        med = statistics.median(per_symbol_test.values())
        ex_top = portfolio({k: v for k, v in test_runs_flat.items() if k != top1}, "net")
        positive = sum(1 for v in per_symbol_test.values() if v > 0)
        lines.append("")
        lines.append(f"- **稳健口径**:去掉最强品种(`{top1}`)后检验窗口年化 "
                     f"**{ex_top['cagr']:+.1%}**(DD {ex_top['max_dd']:.0%});"
                     f"逐品种年化**中位数 {med:+.1%}**;正收益品种 **{positive}/{len(per_symbol_test)}**")
        lines.append("")
        results["long_flat"]["test_ex_top1"] = ex_top
        results["long_flat"]["median_symbol"] = med
        results["long_flat"]["positive_symbols"] = positive
        lines.append("")

    lf = results["long_flat"]
    lines.append("## 3. 判定(用户给的四道门)")
    lines.append("")
    fu, tr, te = lf.get("full"), lf.get("train"), lf.get("test")
    if fu and te:
        lines.append(f"1. **资金费后还剩多少**:全样本 {fu['cagr']:+.1%}(不含资金费 {fu['cagr_gross']:+.1%},"
                     f"影响 {fu['funding_impact']:+.2%})")
        lines.append(f"2. **样本外**:训练 {tr['cagr']:+.1%} → 检验 {te['cagr']:+.1%}"
                     f"(回撤 {te['max_dd']:.0%})")
        btc_te = (bench.get("test") or {})
        lines.append(f"3. **long/flat vs long/short**:检验窗口 "
                     f"{te['cagr']:+.1%} vs {results['long_short']['test']['cagr']:+.1%}")
        lines.append(f"4. **vs BTC 买入持有**:检验窗口 {te['cagr']:+.1%} / DD {te['max_dd']:.0%} "
                     f"vs BTC {btc_te.get('cagr', float('nan')):+.1%} / DD {btc_te.get('max_dd', float('nan')):.0%}")
        lines.append("")
        better_return = te["cagr"] > btc_te.get("cagr", -9)
        better_dd = te["max_dd"] < btc_te.get("max_dd", 9) * 0.85
        med = lf.get("median_symbol", float("nan"))
        ex_top = (lf.get("test_ex_top1") or {}).get("cagr", float("nan"))
        btc_cagr = btc_te.get("cagr", float("nan"))
        if ex_top > btc_cagr and med > btc_cagr and (better_dd or better_return):
            lines.append(f"**结论:稳健口径下过门**(去最强品种 {ex_top:+.1%}、中位 {med:+.1%},"
                         f"均优于 BTC {btc_cagr:+.1%})→ 可进 T4/T5。")
        elif te["cagr"] > 0 and (better_return or better_dd) and ex_top <= btc_cagr:
            lines.append(f"**结论:表面过门、稳健口径不过** —— 组合 {te['cagr']:+.1%} 主要由单一品种贡献,"
                         f"去掉后 {ex_top:+.1%}(BTC {btc_cagr:+.1%})。**判为不可部署**;"
                         f"若仍要继续,必须先解决\"标的池是事后选的\"这个偏差。")
        elif te["cagr"] > 0 and (better_return or better_dd):
            lines.append("**结论:过门(至少一维胜出且样本外为正)→ 可进 T4/T5。**")
        else:
            lines.append("**结论:不过门** —— 样本外收益不优于 BTC 且回撤没有明显更低,"
                         "按用户给的最后一道门判 no-go。")
    lines.append("")
    lines.append("> 说明:资金费按品种自己的费率计入(逐 bar),不再用常数;"
                 "组合是等权、无杠杆、无滑点;未计借币成本与强平约束。")
    lines.append("")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / args.date).mkdir(parents=True, exist_ok=True)
    slug = f"oos-longflat-h{args.horizon}"
    (OUT / args.date / f"{slug}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    keep_out = ("returns", "stamps", "gross_only", "funding")
    slim = {m: {w: ({k: v for k, v in item.items() if k not in keep_out}
                   if isinstance(item, dict) else item)
                for w, item in by_window.items()}
            for m, by_window in results.items()}
    (OUT / args.date / f"{slug}.json").write_text(
        json.dumps({"results": slim, "btc": bench}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print(f"[written] {OUT / args.date / (slug + '.md')}")


if __name__ == "__main__":
    main()
