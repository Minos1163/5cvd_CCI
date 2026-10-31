"""出场参数离线析因回放 (2026-07 ~ 2026-10, 18 个 USDT 永续).

固定入场、只用公开 15m K 线重放出场逻辑, 对三个出场旋钮做 2 x 3 x 2 析因:

  1. stop_floor  in {0.005, 0.010}   stop_pct_eff = max(entry_context.stop_pct, stop_floor)
  2. be_trigger  in {1.0, 1.2, tp1_only}
       1.0 / 1.2 : 浮盈达到 trigger*R 时把止损移到入场价
       tp1_only  : 只有 TP1 成交后才移保本 (账本现状)
  3. bar_rule    in {"stop_first", "tp_first"}  同一根 K 线内"止损与 TP 同时触及"时的仲裁

两种约定的差别只在同根冲突的仲裁, 其余完全一致; 抬升后的止损都在下一根生效:
  stop_first : 同根冲突视为先打止损, 该笔按止损价全平 (保守, 与账本约定一致)
  tp_first   : 同根冲突视为先成交 TP (每根最多一档), 该根不再检查止损

冻结参数严格对齐 src/observability/paper_trading.py 与
scripts/analysis/nearmiss_counterfactual_20261031.py:
  TPi = entry +/- (1.2, 2.0, 3.0) * R,  fraction = (0.40, 0.35, 0.25)
  TP1 成交后止损移到成本价
  MAX_HOLD_BARS = 32 (15m)
  成本 = FEE 5bps + SLIP 5bps, 进出各一次 => 往返 20bps

每个决策同时模拟 LONG 与 SHORT 两个方向 (日志里 side 基本是 NONE), 分别统计后合并。

用法:
  python scripts/analysis/factorial_exit_replay_20261031.py            # 全流程
  python scripts/analysis/factorial_exit_replay_20261031.py --fetch    # 只补 K 线缓存
  python scripts/analysis/factorial_exit_replay_20261031.py --no-fetch # 离线跑 (只用缓存)
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "reports" / "_klines_cache_v2"
OUT_JSON = ROOT / "reports" / "2026-10_factorial_exit.json"
OUT_MD = ROOT / "reports" / "2026-10_factorial_exit.md"

# ---------------- 可调参数 (全部集中在这里) ----------------
SEED = 2026
MAX_SAMPLE = 25_000
STOP_FLOORS = (0.005, 0.010)
BE_TRIGGERS = ("1.0", "1.2", "tp1_only")
BAR_RULES = ("stop_first", "tp_first")

FEE_BPS = 5.0
SLIP_BPS = 5.0
COST_RT = (FEE_BPS + SLIP_BPS) * 2 / 1e4  # 20 bps 往返
TP_LEVELS = (1.2, 2.0, 3.0)
TP_FRACTIONS = (0.40, 0.35, 0.25)
MAX_HOLD_BARS = 32

SYMBOL_EXCLUDE: set[str] = set()  # 如需剔除个别符号, 填在这里并会在报告披露

FETCH_START_MS = 1782604800000  # 2026-06-28T00:00Z
# 注意: 运行环境自带的 HTTPS_PROXY 指向一个对本接口不通的代理(rc=56),
# 因此这里写死任务指定的本地代理, 需要改时用环境变量 KLINE_PROXY。
PROXY = os.environ.get("KLINE_PROXY", "http://127.0.0.1:12334")
FETCH_WORKERS = 3

DECISION_GLOBS = (
    "logs/2026-07/*/decisions.jsonl",
    "logs/2026-08/*/decisions.jsonl",
    "logs/2026-09/*/decisions.jsonl",
    "logs/2026-10/*/decisions.jsonl",
    "logs/2026-10B/2026-10-*/decisions.jsonl",
)

BAR_MS = 15 * 60 * 1000


# ---------------------------------------------------------------- K 线
def _curl(url: str, tries: int = 6) -> list:
    """带重试的请求. 代理偶发 rc=56/52, 必须重试, 否则会静默丢数据."""
    env = dict(os.environ)
    env["HTTPS_PROXY"] = env["HTTP_PROXY"] = PROXY
    env["https_proxy"] = env["http_proxy"] = PROXY
    last_err = ""
    for i in range(tries):
        out = subprocess.run(
            ["curl", "-s", "--compressed", "--max-time", "50", url],
            capture_output=True, text=True, env=env,
        )
        txt = out.stdout.strip()
        if txt:
            try:
                data = json.loads(txt)
            except json.JSONDecodeError as exc:
                last_err = f"json: {exc}"
            else:
                if isinstance(data, dict):
                    raise RuntimeError(f"api error: {data}")
                return data
        else:
            last_err = f"empty rc={out.returncode}"
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"gave up after {tries} tries: {last_err}")


def load_klines(symbol: str, end_ms: int, do_fetch: bool = True) -> list[list]:
    """返回该符号 15m K 线 (按开盘时间升序), 磁盘缓存, 增量补齐."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{symbol}_15m.json"
    bars: list[list] = json.loads(path.read_text()) if path.exists() else []
    if bars:
        bars.sort(key=lambda b: b[0])
    last_ms = bars[-1][0] if bars else None
    need = last_ms is None or last_ms < end_ms - BAR_MS
    if not need:
        return bars
    if not do_fetch:
        print(f"  [warn] {symbol} 缓存不足且 --no-fetch: {len(bars)} 根", flush=True)
        return bars
    cur = (last_ms + BAR_MS) if bars else FETCH_START_MS
    pages = 0
    while cur < end_ms:
        url = (
            f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}"
            f"&interval=15m&startTime={cur}&limit=1500"
        )
        chunk = _curl(url)
        pages += 1
        if not chunk:
            break
        bars.extend(chunk)
        last = chunk[-1][0]
        if last <= cur:
            break
        cur = last + BAR_MS
        if len(chunk) < 1500:
            break
        time.sleep(0.1)
    # 去重 + 排序
    dedup = {b[0]: b for b in bars}
    bars = [dedup[k] for k in sorted(dedup)]
    if bars:  # 部分成功也落盘, 下次增量续传
        path.write_text(json.dumps(bars))
    print(f"  {symbol}: {len(bars)} 根 (+{pages} 页)", flush=True)
    return bars


# ---------------------------------------------------------------- 模拟
def _simulate(
    highs, lows, closes, start_idx, entry: float, sign: float, risk: float,
    be_kind: str, bar_rule: str,
) -> tuple[float, float, str, int]:
    """返回 (毛 R, 成本 R, 出场原因, 持仓根数). R 已按 risk 归一."""
    rnorm = risk / entry  # = stop_pct_eff
    stop = entry - sign * risk
    be_level = None
    if be_kind != "tp1_only":
        be_level = entry + sign * float(be_kind) * risk
    tps = [entry + sign * lvl * risk for lvl in TP_LEVELS]
    remaining = 1.0
    gross = 0.0   # 以 "价格变动占 entry 的比例" 累计, 最后统一 /rnorm
    cost_frac = 0.0
    tp_done = [False, False, False]

    def take(px: float, frac: float) -> None:
        nonlocal remaining, gross, cost_frac
        move = (px - entry) / entry * sign
        gross += frac * move
        cost_frac += frac * COST_RT
        remaining -= frac

    def is_stop_hit(h: float, lo: float) -> bool:
        return (lo <= stop) if sign > 0 else (h >= stop)

    n_end = min(len(highs), start_idx + MAX_HOLD_BARS)
    used = 0
    for j in range(start_idx, n_end):
        h = highs[j]
        lo = lows[j]
        used = j - start_idx + 1

        def favorable() -> bool:
            """有利端: 先触发保本, 再按序吃一档 TP. 返回 True 表示打完."""
            nonlocal stop, remaining
            if be_level is not None and remaining > 0:
                reached = (h >= be_level) if sign > 0 else (lo <= be_level)
                if reached:
                    # 止损上移到成本价 (只上移, 不下移)
                    if (sign > 0 and stop < entry) or (sign < 0 and stop > entry):
                        stop = entry
            for k in range(3):
                if tp_done[k]:
                    continue
                hit = (h >= tps[k]) if sign > 0 else (lo <= tps[k])
                if not hit:
                    continue
                frac = min(remaining, TP_FRACTIONS[k])
                if frac > 0:
                    take(tps[k], frac)
                tp_done[k] = True
                if k == 0 and ((sign > 0 and stop < entry) or (sign < 0 and stop > entry)):
                    stop = entry  # 账本行为: TP1 后移保本
                break
            return remaining <= 1e-9

        if bar_rule == "stop_first":
            # 同根冲突按"先打止损"处理: 止损用本根开始时的水平判定
            if is_stop_hit(h, lo):
                take(stop, remaining)
                return gross / rnorm, cost_frac / rnorm, "STOP", used
            if favorable():
                return gross / rnorm, cost_frac / rnorm, "TP_FULL", used
        else:
            # 同根冲突按"先成交 TP/先触保本"处理: 只在本根确有有利事件时,
            # 才把该根的不利端让位; 没有任何有利事件则止损照常生效.
            # 注意: 止损已经等于入场价时, 保本触发不再算"有利事件", 否则会白送
            # 一根 K 线的免死金牌, 让 be=1.2R 与 tp1_only 产生虚假差异.
            be_active = be_level is not None and remaining > 0 and (
                (sign > 0 and stop < entry) or (sign < 0 and stop > entry)
            )
            favorable_event = any(
                (h >= tps[k]) if sign > 0 else (lo <= tps[k])
                for k in range(3) if not tp_done[k]
            )
            if be_active:
                favorable_event = favorable_event or (
                    (h >= be_level) if sign > 0 else (lo <= be_level)
                )
            if favorable_event:
                if favorable():
                    return gross / rnorm, cost_frac / rnorm, "TP_FULL", used
            elif is_stop_hit(h, lo):
                take(stop, remaining)
                return gross / rnorm, cost_frac / rnorm, "STOP", used

    # 超时: 最后一根收盘平剩余
    px = closes[n_end - 1]
    take(px, remaining)
    return gross / rnorm, cost_frac / rnorm, "TIMEOUT", used


# ---------------------------------------------------------------- 数据
def load_decisions() -> tuple[list[dict], dict]:
    files: list[str] = []
    for g in DECISION_GLOBS:
        files.extend(sorted(glob.glob(str(ROOT / g))))
    files = sorted(set(files))
    seen: set[tuple[str, int]] = set()
    rows: list[dict] = []
    dup = 0
    bad = 0
    total = 0
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    bad += 1
                    continue
                k = d.get("kline") or {}
                sym = d.get("symbol")
                ts = k.get("timestamp")
                sp = (d.get("entry_context") or {}).get("stop_pct")
                if not sym or not ts or not k.get("close") or not sp:
                    bad += 1
                    continue
                if sym in SYMBOL_EXCLUDE:
                    continue
                key = (sym, int(ts))
                if key in seen:
                    dup += 1
                    continue
                seen.add(key)
                rows.append(dict(
                    symbol=sym, ts=int(ts), close=float(k["close"]),
                    stop_pct=float(sp), side=d.get("side"),
                    score=d.get("score"), quadrant=d.get("quadrant"),
                    action=d.get("action"),
                ))
    meta = dict(
        files=len(files), raw_lines=total, uniq=len(rows), dups_dropped=dup, bad_rows=bad,
    )
    return rows, meta


def utc_month(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m")


def utc_date(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d")


def stratified_sample(rows: list[dict], max_n: int, seed: int) -> tuple[list[dict], dict]:
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        strata[(r["symbol"], utc_month(r["ts"]))].append(r)
    for v in strata.values():
        v.sort(key=lambda r: r["ts"])
    total = len(rows)
    if total <= max_n:
        picked = sorted(rows, key=lambda r: (r["symbol"], r["ts"]))
        return picked, dict(mode="census", strata={f"{k[0]}|{k[1]}": len(v) for k, v in sorted(strata.items())})
    rng = random.Random(seed)
    quota = {}
    frac = max_n / total
    for k, v in strata.items():
        quota[k] = min(len(v), max(1, int(round(len(v) * frac))))
    # 修正到 <= max_n
    order = sorted(quota, key=lambda k: (-len(strata[k]), k))
    while sum(quota.values()) > max_n:
        shrunk = False
        for k in order:
            if sum(quota.values()) <= max_n:
                break
            if quota[k] > 1:
                quota[k] -= 1
                shrunk = True
        if not shrunk:
            break
    picked = []
    for k, v in strata.items():
        q = quota[k]
        picked.extend(v if q >= len(v) else rng.sample(v, q))
    picked.sort(key=lambda r: (r["symbol"], r["ts"]))
    detail = {f"{k[0]}|{k[1]}": dict(pop=len(v), taken=quota[k]) for k, v in sorted(strata.items())}
    return picked, dict(mode="stratified", frac=round(frac, 4), strata=detail)


# ---------------------------------------------------------------- 统计
def _cluster_se(vals: list[float], blocks: list[str]) -> tuple[float, int]:
    n = len(vals)
    if n < 2:
        return float("nan"), len(set(blocks))
    m = sum(vals) / n
    acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0])
    for v, b in zip(vals, blocks):
        acc[b][0] += v
        acc[b][1] += 1
    g = len(acc)
    if g < 2:
        return float("nan"), g
    ss = sum((s - c * m) ** 2 for s, c in acc.values())
    var = (g / (g - 1)) * ss / (n * n)
    return math.sqrt(var), g


def summarize(trades: list[dict], wkey: str | None = None) -> dict:
    if not trades:
        return dict(n=0)
    gross = [t["gross_R"] for t in trades]
    cost = [t["cost_R"] for t in trades]
    net = [t["net_R"] for t in trades]
    blocks = [t["block"] for t in trades]
    se, g = _cluster_se(net, blocks)
    se_g, _ = _cluster_se(gross, blocks)
    mean_net = statistics.fmean(net)
    out = dict(
        n=len(net),
        blocks=g,
        gross_mean=round(statistics.fmean(gross), 4),
        gross_se=round(se_g, 4),
        cost_theory_mean=round(statistics.fmean([t["cost_theory"] for t in trades]), 4),
        cost_measured_mean=round(statistics.fmean(cost), 4),
        net_mean=round(mean_net, 4),
        net_median=round(statistics.median(net), 4),
        net_std=round(statistics.pstdev(net), 4) if len(net) > 1 else 0.0,
        net_se=round(se, 4) if se == se else None,
        net_t=round(mean_net / se, 2) if se == se and se > 0 else None,
        gross_median=round(statistics.median(gross), 4),
        gross_std=round(statistics.pstdev(gross), 4) if len(gross) > 1 else 0.0,
        win_rate=round(sum(1 for x in net if x > 0) / len(net), 4),
        avg_hold=round(statistics.fmean([t["hold"] for t in trades]), 2),
        exit_mix={k: round(v / len(net), 4) for k, v in _count(x["exit"] for x in trades).items()},
    )
    if wkey:
        w = [t[wkey] for t in trades]
        sw = sum(w)
        if sw > 0:
            out["net_notional_weighted"] = round(sum(a * b for a, b in zip(w, net)) / sw, 4)
            out["gross_notional_weighted"] = round(sum(a * b for a, b in zip(w, gross)) / sw, 4)
            out["cost_notional_weighted"] = round(sum(a * b for a, b in zip(w, cost)) / sw, 4)
            # 权重归一后仍以 R 为单位, 便于与等权对比
    return out


def _count(it) -> dict:
    d: dict[str, int] = defaultdict(int)
    for x in it:
        d[x] += 1
    return d


def paired_delta(base: list[dict], alt: list[dict], field: str) -> dict:
    """同一批交易成对做差 (alt - base), 按 symbol|utc_date 块聚类算标准误."""
    m = {(t["symbol"], t["ts"], t["side"]): t for t in base}
    diffs: list[float] = []
    blocks: list[str] = []
    for t in alt:
        k = (t["symbol"], t["ts"], t["side"])
        b = m.get(k)
        if b is None:
            continue
        diffs.append(t[field] - b[field])
        blocks.append(t["block"])
    if len(diffs) < 2:
        return dict(n=len(diffs))
    mu = statistics.fmean(diffs)
    se, g = _cluster_se(diffs, blocks)
    return dict(
        n=len(diffs), delta=round(mu, 4),
        se=round(se, 4) if se == se else None,
        t=round(mu / se, 2) if se == se and se > 0 else None,
        blocks=g,
    )


# ---------------------------------------------------------------- 主流程
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="只补 K 线缓存")
    ap.add_argument("--no-fetch", action="store_true", help="不联网, 只用缓存")
    args = ap.parse_args()
    t0 = time.time()

    print("[1/5] 读取决策日志", flush=True)
    rows, dmeta = load_decisions()
    print(f"  唯一决策 {dmeta['uniq']} 条 (原始 {dmeta['raw_lines']} 行, 去重 {dmeta['dups_dropped']}, 坏行 {dmeta['bad_rows']})", flush=True)
    if dmeta["uniq"] == 0:
        print("无可用决策, 退出", flush=True)
        return

    symbols = sorted({r["symbol"] for r in rows})
    lo, hi = min(r["ts"] for r in rows), max(r["ts"] for r in rows)
    print(f"  符号 {len(symbols)}: {', '.join(symbols)}", flush=True)
    print(f"  区间 {dt.datetime.fromtimestamp(lo, dt.timezone.utc)} ~ {dt.datetime.fromtimestamp(hi, dt.timezone.utc)}", flush=True)

    print("[2/5] 拉取/载入 15m K 线", flush=True)
    end_ms = int(time.time() * 1000) + 86400_000
    klines: dict[str, list[list]] = {}
    fetch_fail: dict[str, str] = {}
    if args.no_fetch:
        for s in symbols:
            try:
                klines[s] = load_klines(s, end_ms, do_fetch=False)
            except Exception as exc:  # noqa: BLE001
                fetch_fail[s] = str(exc)[:200]
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _job(sym: str):
            return sym, load_klines(sym, end_ms, do_fetch=True)

        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            futs = {pool.submit(_job, s): s for s in symbols}
            for fut in as_completed(futs):
                sym = futs[fut]
                try:
                    _, bars = fut.result()
                    klines[sym] = bars
                except Exception as exc:  # noqa: BLE001
                    fetch_fail[sym] = str(exc)[:200]
                    print(f"  [FAIL] {sym}: {exc}", flush=True)
    if args.fetch:
        print("--fetch 模式结束", flush=True)
        return

    idx: dict[str, dict[int, int]] = {}
    for s, bars in klines.items():
        idx[s] = {int(b[0] // 1000): i for i, b in enumerate(bars)}

    print("[3/5] 分层抽样", flush=True)
    sample, smeta = stratified_sample(rows, MAX_SAMPLE, SEED)
    print(f"  抽样 {len(sample)} 条 mode={smeta['mode']}", flush=True)

    print("[4/5] 析因回放", flush=True)
    cells: dict[tuple, list[dict]] = defaultdict(list)
    missing_bar = 0
    truncated = 0
    no_window = 0
    used_syms: set[str] = set()
    used_days: set[str] = set()
    kmin: dict[str, int] = {}
    kmax: dict[str, int] = {}
    for s, bars in klines.items():
        if bars:
            kmin[s] = int(bars[0][0] // 1000)
            kmax[s] = int(bars[-1][0] // 1000)

    n_done = 0
    for r in sample:
        s = r["symbol"]
        bars = klines.get(s) or []
        m = idx.get(s) or {}
        if r["ts"] not in m:
            missing_bar += 1
            continue
        i0 = m[r["ts"]]
        avail = min(len(bars) - i0 - 1, MAX_HOLD_BARS)
        if avail < MAX_HOLD_BARS:
            truncated += 1
            continue
        highs = [float(b[2]) for b in bars[i0 + 1: i0 + 1 + MAX_HOLD_BARS]]
        lows = [float(b[3]) for b in bars[i0 + 1: i0 + 1 + MAX_HOLD_BARS]]
        closes = [float(b[4]) for b in bars[i0 + 1: i0 + 1 + MAX_HOLD_BARS]]
        entry = r["close"]
        block = f"{s}|{utc_date(r['ts'])}"
        used_syms.add(s)
        used_days.add(utc_date(r["ts"]))
        n_done += 1
        for floor in STOP_FLOORS:
            sp = max(r["stop_pct"], floor)
            risk = entry * sp
            if risk <= 0:
                continue
            for be in BE_TRIGGERS:
                for rule in BAR_RULES:
                    for side, sign in (("LONG", 1.0), ("SHORT", -1.0)):
                        g, c, why, hold = _simulate(highs, lows, closes, 0, entry, sign, risk, be, rule)
                        cells[(floor, be, rule)].append(dict(
                            symbol=s, side=side, block=block, ts=r["ts"],
                            stop_pct_eff=sp, exit=why, hold=hold,
                            gross_R=g, cost_R=c, net_R=g - c,
                            cost_theory=COST_RT / sp,
                            w=1.0 / sp,  # 等风险预算下的 notional 权重
                        ))
        if n_done % 2000 == 0:
            print(f"  {n_done}/{len(sample)} ({time.time()-t0:.0f}s)", flush=True)

    print(f"  模拟完成: {n_done} 条决策 x2 方向, 耗时 {time.time()-t0:.0f}s", flush=True)

    print("[5/5] 汇总", flush=True)
    cell_out = []
    for floor in STOP_FLOORS:
        for be in BE_TRIGGERS:
            for rule in BAR_RULES:
                tr = cells[(floor, be, rule)]
                if not tr:
                    continue
                by_side = {}
                for sd in ("LONG", "SHORT"):
                    sub = [t for t in tr if t["side"] == sd]
                    by_side[sd] = summarize(sub, "w")
                cell_out.append(dict(
                    stop_floor=floor, be_trigger=be, bar_rule=rule,
                    all=summarize(tr, "w"),
                    by_side=by_side,
                ))

    # ---- 成对做差 (同一批交易, 按块聚类) ----
    deltas: list[dict] = []
    for be in BE_TRIGGERS:
        for rule in BAR_RULES:
            a = cells[(STOP_FLOORS[0], be, rule)]
            b = cells[(STOP_FLOORS[1], be, rule)]
            for fld in ("gross_R", "cost_R", "net_R"):
                d = paired_delta(a, b, fld)
                d.update(kind="stop_floor", base=f"{STOP_FLOORS[0]:.3f}", alt=f"{STOP_FLOORS[1]:.3f}",
                         be_trigger=be, bar_rule=rule, field=fld)
                deltas.append(d)
    for floor in STOP_FLOORS:
        for rule in BAR_RULES:
            base = cells[(floor, "tp1_only", rule)]
            for be in ("1.0", "1.2"):
                alt = cells[(floor, be, rule)]
                for fld in ("gross_R", "net_R"):
                    d = paired_delta(base, alt, fld)
                    d.update(kind="be_trigger", base="tp1_only", alt=be,
                             stop_floor=floor, bar_rule=rule, field=fld)
                    deltas.append(d)
    for floor in STOP_FLOORS:
        for be in BE_TRIGGERS:
            base = cells[(floor, be, BAR_RULES[0])]
            alt = cells[(floor, be, BAR_RULES[1])]
            for fld in ("gross_R", "net_R"):
                d = paired_delta(base, alt, fld)
                d.update(kind="bar_rule", base=BAR_RULES[0], alt=BAR_RULES[1],
                         stop_floor=floor, be_trigger=be, field=fld)
                deltas.append(d)

    raw_sp = sorted(r["stop_pct"] for r in sample)
    sp_profile = dict(
        n=len(raw_sp),
        min=round(raw_sp[0], 5),
        p50=round(raw_sp[len(raw_sp) // 2], 5),
        p90=round(raw_sp[int(len(raw_sp) * 0.9)], 5),
        max=round(raw_sp[-1], 5),
        share_eq_0005=round(sum(1 for x in raw_sp if abs(x - 0.005) < 1e-9) / len(raw_sp), 4),
        share_gt_0005=round(sum(1 for x in raw_sp if x > 0.005 + 1e-9) / len(raw_sp), 4),
        widened_by_floor_0010=round(sum(1 for x in raw_sp if x < 0.010) / len(raw_sp), 4),
        mean_cost_R_floor_0005=round(statistics.fmean(COST_RT / max(x, 0.005) for x in raw_sp), 4),
        mean_cost_R_floor_0010=round(statistics.fmean(COST_RT / max(x, 0.010) for x in raw_sp), 4),
    )

    coverage = dict(
        symbols_total=len(symbols),
        symbols_used=len(used_syms),
        symbols_fetch_fail=sorted(fetch_fail),
        fetch_fail_detail=fetch_fail,
        symbols_zero_kline=sorted(s for s in symbols if not klines.get(s)),
        kline_first={s: dt.datetime.fromtimestamp(v, dt.timezone.utc).isoformat() for s, v in sorted(kmin.items())},
        kline_last={s: dt.datetime.fromtimestamp(v, dt.timezone.utc).isoformat() for s, v in sorted(kmax.items())},
        decisions_in_sample=len(sample),
        decisions_simulated=n_done,
        dropped_missing_entry_bar=missing_bar,
        dropped_truncated_window=truncated,
        utc_days_covered=len(used_days),
        blocks_total=len({t["block"] for tr in cells.values() for t in tr}),
        trades_per_cell=len(cells[(STOP_FLOORS[0], BE_TRIGGERS[0], BAR_RULES[0])]),
        stop_pct_profile=sp_profile,
    )
    payload = dict(
        meta=dict(
            generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            seed=SEED, max_sample=MAX_SAMPLE,
            stop_floors=list(STOP_FLOORS), be_triggers=list(BE_TRIGGERS),
            bar_rules=list(BAR_RULES),
            tp_levels=list(TP_LEVELS), tp_fractions=list(TP_FRACTIONS),
            max_hold_bars=MAX_HOLD_BARS,
            fee_bps=FEE_BPS, slip_bps=SLIP_BPS, cost_rt=COST_RT,
            decision_meta=dmeta, sampling=smeta, coverage=coverage,
            runtime_sec=round(time.time() - t0, 1),
        ),
        cells=cell_out,
        deltas=deltas,
    )
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  写出 {OUT_JSON.relative_to(ROOT)}", flush=True)

    for c in cell_out:
        a = c["all"]
        print(
            f"  floor={c['stop_floor']:.3f} be={c['be_trigger']:>8s} {c['bar_rule']:>10s} "
            f"n={a['n']:>6d} gross={a['gross_mean']:+.3f} cost={a['cost_measured_mean']:.3f} "
            f"net={a['net_mean']:+.3f} se={a['net_se']} blocks={a['blocks']}",
            flush=True,
        )
    print(f"总耗时 {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    sys.exit(main())
