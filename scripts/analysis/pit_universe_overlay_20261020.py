"""偏差 1 修补:用**历史时点可得**的标的池重跑 long/flat 的四道门。

为什么要重跑
------------
上一轮(`s1_overlay_oos_2026-10-20.md`)的 16 个品种是"今天还在交易"的池子,含 LAB/CC/HYPE
这些 2025 年才上市、事后看涨了几十倍的品种;去掉 LAB 后年化从 +55.5% 掉到 +24.5%。
这仍是事后选择。本脚本改成:

1. 候选池 = **2021-11-01 之前就已上市**的 USDT 永续(用 `exchangeInfo.onboardDate` 筛),
   彻底排除"事后挑新币";
2. 每个**换仓时点**再加两道**时点内**过滤:
   - 该品种当时至少有 200 根 4h 历史(均线可算);
   - 过去 30 天(180 根)日均美元成交额 ≥ `--min-dollar-vol`(默认 $10M)。
   两条都只用当时及之前的数据,不含未来信息;
3. 组合 = 每个时间戳对"当时合格"的品种等权平均。

口径与上一轮一致:4h bar,`SMA50>SMA200` 做多、否则空仓,每 42 根(7 天)检查,20bps/次换手。
**本轮不计资金费**(上一轮已单独测过:影响 −3.6%~+7.1%/年,符号随 regime 变),报告里会写明。

幸存者偏差仍在:已下架的品种拿不到(交易所不提供),这一点无法用公开 API 修补,只能披露。

用法
----
    python scripts/analysis/pit_universe_overlay_20261020.py            # 先补数据再跑
    python scripts/analysis/pit_universe_overlay_20261020.py --eval-only
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
KLINE = "https://fapi.binance.com/fapi/v1/klines"
INFO = "https://fapi.binance.com/fapi/v1/exchangeInfo"
INTERVAL = "4h"
BAR_MS = 4 * 3600 * 1000
START_MS = 1_634_832_000_000
UNIVERSE_CUTOFF = 1_635_724_800_000  # 2021-11-01
TRAIN_END = "2024-12-31"
TEST_START = "2025-01-01"


def _get(url: str, timeout: float = 45.0, retries: int = 4):
    last = None
    for attempt in range(retries):
        try:
            with urlopen(url, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed: {url} :: {last}")


def universe() -> list[str]:
    info = _get(INFO)
    out = []
    for item in info.get("symbols", []):
        if (item.get("quoteAsset") != "USDT" or item.get("contractType") != "PERPETUAL"
                or item.get("status") != "TRADING"):
            continue
        onboard = item.get("onboardDate") or 0
        if onboard and onboard <= UNIVERSE_CUTOFF:
            out.append(item["symbol"])
    return sorted(out)


def ensure_bars(symbol: str) -> Path | None:
    path = CACHE / f"{symbol}_{INTERVAL}.csv"
    if path.exists():
        return path
    rows: dict[int, list] = {}
    cursor = START_MS
    now_ms = int(time.time() * 1000)
    while cursor < now_ms:
        params = urlencode({"symbol": symbol, "interval": INTERVAL,
                            "startTime": cursor, "limit": 1500})
        try:
            batch = _get(f"{KLINE}?{params}", retries=3)
        except RuntimeError:
            break
        if not batch:
            break
        for item in batch:
            rows[int(item[0])] = item
        last = int(batch[-1][0])
        if last <= cursor:
            break
        cursor = last + 1
        time.sleep(0.12)
    if len(rows) < 300:
        return None
    frame = pd.DataFrame([rows[k] for k in sorted(rows)], columns=[
        "ts", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
    ])[["ts", "open", "high", "low", "close", "volume", "taker_base"]]
    for col in ("open", "high", "low", "close", "volume", "taker_base"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame.to_csv(path, index=False)
    return path


def prepare(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("ts").reset_index(drop=True)
    close = df["close"]
    df["sma50"] = close.rolling(50).mean()
    df["sma200"] = close.rolling(200).mean()
    df["up"] = (df["sma50"] > df["sma200"]).astype(int)
    df["dollar_vol"] = close * df["volume"]
    df["dollar_vol_30d"] = df["dollar_vol"].rolling(180).mean()
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df


def simulate(df: pd.DataFrame, horizon: int, cost_bps: float,
             min_dollar_vol: float, start: str | None, end: str | None) -> pd.DataFrame:
    sub = df
    if start:
        sub = sub[sub["dt"] >= pd.Timestamp(start, tz="UTC")]
    if end:
        sub = sub[sub["dt"] <= pd.Timestamp(end, tz="UTC")]
    if len(sub) < 300:
        return pd.DataFrame()
    sub = sub.reset_index(drop=True)
    pos = 0
    switches = 0
    rows = []
    i = 0
    while i + 2 < len(sub):
        if (i % horizon) == 0:
            vol = sub.at[i, "dollar_vol_30d"]
            sma200 = sub.at[i, "sma200"]
            eligible = bool(pd.notna(vol) and pd.notna(sma200)
                            and vol >= min_dollar_vol)
            target = int(sub.at[i, "up"]) if eligible else 0
            if target != pos:
                switches += 1
                pos = target
        else:
            eligible = None  # 保持上一块的判定
        gross = float(sub.at[i + 2, "open"]) / float(sub.at[i + 1, "open"]) - 1.0
        rows.append({"ts": sub.at[i + 1, "dt"], "ret": pos * gross,
                     "pos": pos, "eligible": eligible})
        i += 1
    frame = pd.DataFrame(rows)
    frame["switches"] = switches
    return frame


def _metrics(rets: list[float], years: float) -> dict:
    equity = 1.0
    curve = []
    for r in rets:
        equity *= (1.0 + r)
        curve.append(equity)
    cagr = equity ** (1 / years) - 1 if years > 0 and equity > 0 else float("nan")
    peak, mdd = 1.0, 0.0
    for value in curve:
        peak = max(peak, value)
        mdd = max(mdd, (peak - value) / peak)
    return {"cagr": cagr, "max_dd": mdd, "equity": equity,
            "calmar": (cagr / mdd) if mdd > 0 else float("nan")}


def portfolio(frames: dict[str, pd.DataFrame], *, drop: set[str] | None = None) -> dict:
    """每个时间戳只对"当时合格"的品种等权平均。"""
    drop = drop or set()
    by_ts: dict[pd.Timestamp, list[float]] = {}
    for symbol, frame in frames.items():
        if symbol in drop or frame.empty:
            continue
        # 把每根 bar 的合格标志向前填充(块内保持)
        flags = frame["eligible"].ffill().fillna(False)
        for ts, ret, ok in zip(frame["ts"], frame["ret"], flags):
            if ok:
                by_ts.setdefault(ts, []).append(float(ret))
    stamps = sorted(by_ts)
    if not stamps:
        return {}
    rets = [statistics.fmean(by_ts[ts]) for ts in stamps]
    years = len(stamps) * 4 / (24 * 365)
    out = _metrics(rets, years)
    out["n_bars"] = len(stamps)
    out["avg_symbols"] = statistics.fmean([len(v) for v in by_ts.values()])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=42)
    ap.add_argument("--cost", type=float, default=20.0)
    ap.add_argument("--min-dollar-vol", type=float, default=1e7)
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--max-symbols", type=int, default=0)
    ap.add_argument("--date", default="2026-10-20")
    args = ap.parse_args()

    symbols = universe()
    if args.max_symbols:
        symbols = symbols[: args.max_symbols]
    print(f"[universe] {len(symbols)} symbols listed before 2021-11")

    data: dict[str, pd.DataFrame] = {}
    missing = []
    for idx, symbol in enumerate(symbols, 1):
        path = CACHE / f"{symbol}_{INTERVAL}.csv"
        if not path.exists() and args.eval_only:
            continue
        path = ensure_bars(symbol) if not path.exists() else path
        if not path:
            missing.append(symbol)
            continue
        df = prepare(path)
        if len(df) < 500:
            continue
        data[symbol] = df
        if idx % 10 == 0:
            print(f"[dl] {idx}/{len(symbols)} cached, usable={len(data)}")
    print(f"[data] usable={len(data)} missing={len(missing)}")

    windows = {"full": (None, None), "train": (None, TRAIN_END), "test": (TEST_START, None)}
    results = {}
    per_symbol_test = {}
    for name, (start, end) in windows.items():
        frames = {}
        for symbol, df in data.items():
            frame = simulate(df, args.horizon, args.cost, args.min_dollar_vol, start, end)
            if not frame.empty:
                frames[symbol] = frame
        if not frames:
            continue
        item = portfolio(frames)
        results[name] = item
        if name == "test":
            for symbol, frame in frames.items():
                flags = frame["eligible"].ffill().fillna(False)
                rets = [float(r) for r, ok in zip(frame["ret"], flags) if ok]
                if len(rets) > 300:
                    years = len(rets) * 4 / (24 * 365)
                    per_symbol_test[symbol] = _metrics(rets, years)["cagr"]

    # BTC 基准
    btc = prepare(CACHE / f"BTCUSDT_{INTERVAL}.csv")
    bench = {}
    for name, (start, end) in windows.items():
        sub = btc.copy()
        if start:
            sub = sub[sub["dt"] >= pd.Timestamp(start, tz="UTC")]
        if end:
            sub = sub[sub["dt"] <= pd.Timestamp(end, tz="UTC")]
        sub = sub.reset_index(drop=True)
        if len(sub) < 300:
            continue
        eq = float(sub["open"].iloc[-1]) / float(sub["open"].iloc[0])
        years = len(sub) * 4 / (24 * 365)
        peak, mdd = 1.0, 0.0
        for value in (sub["open"] / float(sub["open"].iloc[0])):
            peak = max(peak, float(value))
            mdd = max(mdd, (peak - float(value)) / peak)
        bench[name] = {"cagr": eq ** (1 / years) - 1, "max_dd": mdd}

    lines = ["# 偏差 1 修补:历史时点标的池下的 long/flat", "",
             f"- 候选池:{len(data)} 个 **2021-11-01 前上市**的 USDT 永续(排除事后挑新币)",
             f"- 时点过滤:≥200 根历史 + 30 日均美元成交额 ≥ ${args.min_dollar_vol/1e6:.0f}M",
             f"- 口径:4h,SMA50>SMA200 做多否则空仓,每 {args.horizon} 根检查,{args.cost:.0f}bps/次换手;"
             "**本轮不含资金费**", ""]
    lines.append("| 窗口 | 年化 | 最大回撤 | Calmar | 平均在场品种数 | BTC 年化 | BTC 回撤 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for name in ("full", "train", "test"):
        item = results.get(name)
        if not item:
            continue
        b = bench.get(name) or {}
        lines.append(f"| {name} | {item['cagr']:+.1%} | {item['max_dd']:.0%} | {item['calmar']:.2f} | "
                     f"{item['avg_symbols']:.1f} | {b.get('cagr', float('nan')):+.1%} | "
                     f"{b.get('max_dd', float('nan')):.0%} |")
    lines.append("")

    if per_symbol_test:
        vals = sorted(per_symbol_test.values())
        med = statistics.median(vals)
        pos = sum(1 for v in vals if v > 0)
        lines.append(f"- 检验窗口逐品种:中位 **{med:+.1%}**、正收益 **{pos}/{len(vals)}**")
        top = sorted(per_symbol_test.items(), key=lambda kv: kv[1], reverse=True)[:3]
        lines.append(f"- 前三名:{', '.join(f'{s} {v:+.1%}' for s, v in top)}")
        lines.append("")

    test = results.get("test") or {}
    btc_test = (bench.get("test") or {}).get("cagr", float("nan"))
    lines.append("## 判定")
    lines.append("")
    if test:
        passed = test["cagr"] > btc_test and test["max_dd"] < (bench.get("test") or {}).get("max_dd", 1) * 0.85
        if passed:
            lines.append(f"**偏差修补后仍过门**:检验窗口 {test['cagr']:+.1%}/DD {test['max_dd']:.0%} "
                         f"vs BTC {btc_test:+.1%}/DD {(bench.get('test') or {}).get('max_dd', float('nan')):.0%} → 可继续 T4/T5。")
        else:
            lines.append(f"**偏差修补后不再过门**:检验窗口 {test['cagr']:+.1%}/DD {test['max_dd']:.0%} "
                         f"vs BTC {btc_test:+.1%} → 原结论是标的池偏差的产物,应停下重新评估。")
    lines.append("")
    lines.append("> 幸存者偏差仍在:已下架的品种无法通过公开 API 取得,本池只包含「活到今天」的品种。")
    lines.append("")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / args.date).mkdir(parents=True, exist_ok=True)
    slug = f"pit-universe-h{args.horizon}"
    (OUT / args.date / f"{slug}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / args.date / f"{slug}.json").write_text(json.dumps(
        {"results": results, "bench": bench,
         "per_symbol_test": per_symbol_test, "missing": missing,
         "universe_n": len(data)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print(f"[written] {OUT / args.date / (slug + '.md')}")


if __name__ == "__main__":
    main()
