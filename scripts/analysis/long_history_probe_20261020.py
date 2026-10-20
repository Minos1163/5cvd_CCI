"""长历史毛边际探针(4h/1d):先回答"方向规则在长周期上到底有没有毛 bps"。

为什么先做这个
--------------
8 周日志已经无法区分"信号"与"成本几何"(见 v3 §1):
- 安慰剂的正效应来自 `t'<t` 的前视泄漏;
- 组件 IC 的"正号"是 `R_net` 里成本项贡献的。

所以第一步不是造新指标,而是**换数据规模**:用 2021 年以来公开的 4h K 线,
直接在原始 bar 上算"方向规则 + 固定持有期"的**毛 bps**,再看它够不够覆盖
10/20/30bps 的往返成本。全部因果:方向用 `t` 及之前的 bar,入场用 `t+1` 开盘。

四个方向规则(都只用过去信息)
------------------------------
R1 `ema200`   : d = sign(close_t − EMA200_t)
R2 `sma50_200`: d = +1 if SMA50>SMA200 else −1
R3 `donch20`  : d = sign(close_t − (max(high,20)+min(low,20))/2)
R4 `mom6`     : d = sign(close_t / close_{t−6} − 1)

持有期(4h 根):6 / 12 / 24 / 42 / 60(= 1 / 2 / 4 / 7 / 10 天)

口径说明(重要)
----------------
- 重叠样本会低估方差:除全样本外,另给 **非重叠** 子样本(按 index % h 取),
  `n_eff` 按非重叠样本数报,显著性只认非重叠口径。
- 按 UTC 日做块 bootstrap 给 80% CI;跨品种汇总用等权平均,并在符号一致性上
  单独报告(≥3 个品种同号为"方向一致")。
- 成本不进入毛 bps;报告里单列 10/20/30bps 三档的净结果,**不做"扣费后仍为正"
  的隐含假设**。

用法
----
    python scripts/analysis/long_history_probe_20261020.py            # 有缓存则直接评估
    python scripts/analysis/long_history_probe_20261020.py --refresh  # 强制重下

产出
----
`logs/analysis/long-history/2026-10-20/report.md` 与 `metrics.json`。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
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

BASE = "https://fapi.binance.com/fapi/v1/klines"
CACHE = ROOT / "data" / "history"
REPORT_ROOT = ROOT / "logs" / "analysis" / "long-history"

#: 当前运行的标的 + 两个基准(缺历史的会自动缩短,报告里披露起始日)
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT", "TRXUSDT",
    "HYPEUSDT", "DOGEUSDT", "ZECUSDT", "XLMUSDT", "ADAUSDT", "XMRUSDT",
    "LINKUSDT", "CCUSDT", "LABUSDT", "TONUSDT",
]
INTERVAL = "4h"
BAR_HOURS = 4
START_MS = 1_634_832_000_000  # 2021-10-21,5 年窗口的起点
HORIZONS = [6, 12, 24, 42, 60]
COSTS = [10.0, 20.0, 30.0]
RULES = ["ema200", "sma50_200", "donch20", "mom6"]


def _get(url: str, timeout: float = 30.0, retries: int = 3):
    last = None
    for attempt in range(retries):
        try:
            with urlopen(url, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request failed: {url} :: {last}")


def download(symbol: str, *, refresh: bool = False) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{symbol}_{INTERVAL}.csv"
    if path.exists() and not refresh:
        return path
    rows: dict[int, list] = {}
    cursor = START_MS
    now_ms = int(time.time() * 1000)
    while cursor < now_ms:
        params = urlencode({"symbol": symbol, "interval": INTERVAL,
                            "startTime": cursor, "limit": 1500})
        batch = _get(f"{BASE}?{params}")
        if not batch:
            break
        for item in batch:
            rows[int(item[0])] = item
        last_open = int(batch[-1][0])
        if last_open <= cursor:
            break
        cursor = last_open + 1
        time.sleep(0.15)
    ordered = [rows[k] for k in sorted(rows)]
    frame = pd.DataFrame(ordered, columns=[
        "ts", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
    ])
    frame = frame[["ts", "open", "high", "low", "close", "volume", "taker_base"]]
    for col in ("open", "high", "low", "close", "volume", "taker_base"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame.to_csv(path, index=False)
    print(f"[dl] {symbol}: {len(frame)} bars "
          f"{pd.to_datetime(frame['ts'].iloc[0], unit='ms')} → "
          f"{pd.to_datetime(frame['ts'].iloc[-1], unit='ms')}")
    return path


def prepare(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("ts").reset_index(drop=True)
    close = df["close"]
    df["ema200"] = close.ewm(span=200, adjust=False).mean()
    df["sma50"] = close.rolling(50).mean()
    df["sma200"] = close.rolling(200).mean()
    high20 = df["high"].rolling(20).max()
    low20 = df["low"].rolling(20).min()
    df["donch_mid"] = (high20 + low20) / 2.0
    df["mom6"] = close / close.shift(6) - 1.0
    df["date"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.strftime("%Y-%m-%d")
    df["dir_ema200"] = (close - df["ema200"]).apply(lambda v: 1 if v > 0 else (-1 if v < 0 else 0))
    df["dir_sma50_200"] = (df["sma50"] - df["sma200"]).apply(lambda v: 1 if v > 0 else (-1 if v < 0 else 0))
    df["dir_donch20"] = (close - df["donch_mid"]).apply(lambda v: 1 if v > 0 else (-1 if v < 0 else 0))
    df["dir_mom6"] = df["mom6"].apply(lambda v: 1 if v > 0 else (-1 if v < 0 else 0))
    return df


def forward_bps(df: pd.DataFrame, horizon: int) -> pd.Series:
    """t+1 开盘入场,t+1+h 开盘出场(都以开盘价计,避免收盘价的同 bar 幻觉)。"""
    entry = df["open"].shift(-1)
    exit_ = df["open"].shift(-(1 + horizon))
    return (exit_ / entry - 1.0) * 1e4


def evaluate_symbol(symbol: str, df: pd.DataFrame) -> list[dict]:
    out: list[dict] = []
    for horizon in HORIZONS:
        fwd = forward_bps(df, horizon)
        # 基准:永远做多。5 年窗口是大牛市,任何"多数时间在场"的规则都会白捡 beta,
        # 所以必须把"超额(相对永远做多)"单列,否则会把 beta 当成 alpha。
        valid_base = fwd.dropna()
        base_idx = [i for i in valid_base.index if i % horizon == 0]
        base_bps = float(valid_base.loc[base_idx].mean()) if base_idx else float("nan")
        for rule in RULES:
            direction = df[f"dir_{rule}"]
            mask = direction.notna() & fwd.notna() & (direction != 0)
            if not mask.any():
                continue
            gross = direction[mask] * fwd[mask]
            idx = list(gross.index)
            # 非重叠:按绝对 index 取模,近似"每 horizon 根只留一个样本"
            non_overlap = [i for i in idx if i % horizon == 0]
            if len(non_overlap) < 30:
                continue
            sample = gross.loc[non_overlap]
            long_share = float((direction.loc[non_overlap] > 0).mean())
            by_day: dict[str, list[float]] = {}
            for i, value in sample.items():
                by_day.setdefault(df.at[i, "date"], []).append(float(value))
            out.append({
                "symbol": symbol,
                "rule": rule,
                "horizon": horizon,
                "n_all": int(len(gross)),
                "n_eff": int(len(sample)),
                "days": len(by_day),
                "mean_bps": float(sample.mean()),
                "base_bps": base_bps,
                "excess_bps": float(sample.mean()) - base_bps,
                "long_share": long_share,
                "sd_bps": float(sample.std(ddof=1)) if len(sample) > 2 else None,
                "t": float(sample.mean() / (sample.std(ddof=1) / math.sqrt(len(sample))))
                if len(sample) > 2 and sample.std(ddof=1) > 0 else None,
                "hit": float((sample > 0).mean()),
                "_by_day": {k: v for k, v in by_day.items()},
            })
    return out


def _day_bootstrap(rows: list[dict], *, iters: int = 2000, seed: int = 7,
                   lo: float = 0.10, hi: float = 0.90) -> tuple[float, float]:
    """把同 rule/horizon 的 day→values 合并后做日块 bootstrap。"""
    pooled: dict[str, list[float]] = {}
    for row in rows:
        for day, values in row["_by_day"].items():
            pooled.setdefault(f"{row['symbol']}|{day}", []).extend(values)
    keys = list(pooled)
    if len(keys) < 20:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(iters):
        pick = [keys[rng.randrange(len(keys))] for _ in keys]
        flat = [v for k in pick for v in pooled[k]]
        if flat:
            means.append(sum(flat) / len(flat))
    means.sort()
    return (means[int(lo * (len(means) - 1))], means[int(hi * (len(means) - 1))])


def build_report(cells: list[dict], spans: dict[str, tuple[str, str, int]]) -> str:
    lines: list[str] = ["# 长历史毛边际探针(4h)", "",
                        f"- 窗口:2021-10 起,数据截止见各品种跨度",
                        f"- 规则:{', '.join(RULES)};持有期(根):{HORIZONS}",
                        "- 口径:t 收盘定方向,**t+1 开盘入场**,t+1+h 开盘出场;非重叠子样本定显著性",
                        ""]
    lines.append("## 1. 数据跨度")
    lines.append("")
    lines.append("| 品种 | 起始 | 结束 | 根数 |")
    lines.append("|---|---|---|---:|")
    for symbol, (first, last, n) in spans.items():
        lines.append(f"| {symbol} | {first} | {last} | {n} |")
    lines.append("")

    lines.append("## 2. 跨品种汇总(等权)")
    lines.append("")
    lines.append("> 基准 = **永远做多**同一持有期的毛 bps。5 年窗口是牛市,"
                 "任何多数时间在场的规则都会白捡 beta;`超额` 才是方向规则的贡献。")
    lines.append("")
    header = ("| 规则 | 持有(根) | 品种数 | 毛 bps | 基准 | 超额 | 净@20(毛) | 净@20(超额) | "
              "同号(毛/超额) | 80% CI(超额,日块) |")
    lines.append(header)
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    grouped: dict[tuple[str, int], list[dict]] = {}
    for cell in cells:
        grouped.setdefault((cell["rule"], cell["horizon"]), []).append(cell)
    rows_out = []
    for key in sorted(grouped, key=lambda k: (HORIZONS.index(k[1]), RULES.index(k[0]))):
        rows = grouped[key]
        means = [r["mean_bps"] for r in rows]
        excess = [r["excess_bps"] for r in rows]
        avg = statistics.fmean(means)
        avg_ex = statistics.fmean(excess)
        base = statistics.fmean([r["base_bps"] for r in rows])
        same = sum(1 for m in means if m > 0)
        same_ex = sum(1 for m in excess if m > 0)
        # 超额口径的日块 CI:把每格换成"实际 − 该品种基准"
        shifted = []
        for r in rows:
            item = dict(r)
            item["_by_day"] = {k: [v - r["base_bps"] for v in vals]
                               for k, vals in r["_by_day"].items()}
            shifted.append(item)
        ci = _day_bootstrap(shifted)
        ci_text = "-" if math.isnan(ci[0]) else f"[{ci[0]:+.1f}, {ci[1]:+.1f}]"
        rows_out.append((key, avg, avg_ex, same, same_ex, len(rows), ci, ci_text, base))
        lines.append(f"| {key[0]} | {key[1]} | {len(rows)} | {avg:+.1f} | {base:+.1f} | "
                     f"**{avg_ex:+.1f}** | {avg-20:+.1f} | {avg_ex-20:+.1f} | "
                     f"{same}/{len(rows)} · {same_ex}/{len(rows)} | {ci_text} |")
    lines.append("")

    best = max(rows_out, key=lambda item: item[2]) if rows_out else None
    lines.append("## 3. 判定")
    lines.append("")
    if best is None:
        lines.append("没有可用格子(样本不足)。")
    else:
        (rule, horizon), avg, avg_ex, same, same_ex, n, ci, ci_text, base = best
        lines.append(f"- 超额最好的一格:`{rule}` / 持有 {horizon} 根(≈{horizon*BAR_HOURS/24:.1f} 天)"
                     f",跨 {n} 个品种:**毛 {avg:+.1f} bps / 基准 {base:+.1f} / 超额 {avg_ex:+.1f} bps**"
                     f",同号 {same}/{n}(超额 {same_ex}/{n}),80% CI(超额) {ci_text}")
        lines.append(f"- 扣 20bps:净@20(毛) **{avg-20:+.1f}** / 净@20(超额) **{avg_ex-20:+.1f}**")
        lines.append("")
        if avg_ex - 20 > 0 and same_ex >= max(3, int(0.6 * n)) and ci[0] > 0:
            lines.append("**结论:超额在 20bps 后仍为正、多数品种同号、日块 CI 下界 >0 → "
                         "值得进入 G1′(有效片段 ≥2,000)复核。**")
        elif avg_ex - 20 > 0:
            lines.append("**结论:超额均值为正但不够稳(同号不足或 CI 跨 0)→ 不能作为候选,"
                         "需按品种/时段分层再看。**")
        else:
            lines.append("**结论:扣 20bps 后超额 ≤0 → 方向规则只是 beta 的另一种表达,"
                         "按 G1′/G3′ 判 no-go。**")
    lines.append("")
    lines.append("> 说明:等权平均会掩盖品种差异;同号品种数是最低限度的稳健性检查。"
                 "`n_eff` 见 metrics.json,显著性只按非重叠子样本解释。")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--symbols", default="")
    ap.add_argument("--date", default="2026-10-20")
    args = ap.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or SYMBOLS
    spans: dict[str, tuple[str, str, int]] = {}
    cells: list[dict] = []

    for symbol in symbols:
        try:
            path = download(symbol, refresh=args.refresh)
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {symbol}: {exc}")
            continue
        df = prepare(path)
        if len(df) < 500:
            print(f"[skip] {symbol}: only {len(df)} bars")
            continue
        first = str(pd.to_datetime(df['ts'].iloc[0], unit='ms'))[:10]
        last = str(pd.to_datetime(df['ts'].iloc[-1], unit='ms'))[:10]
        spans[symbol] = (first, last, len(df))
        cells.extend(evaluate_symbol(symbol, df))
        print(f"[eval] {symbol}: {len(df)} bars, {first} → {last}")

    if not cells:
        raise SystemExit("no cells evaluated")

    out_dir = REPORT_ROOT / args.date
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(cells, spans)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    slim = [{k: v for k, v in c.items() if k != "_by_day"} for c in cells]
    (out_dir / "metrics.json").write_text(
        json.dumps({"spans": spans, "cells": slim}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(report)
    print(f"[written] {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
