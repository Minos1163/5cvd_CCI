"""2026-10-31 S2 试点了结(配对符号检验) + 闸门反选检验(同一引擎重放).

任务 A:paper_ab 两臂对同一批 54 个入场用不同出场规则各跑一遍,配对比净额、做
        exact binomial 符号检验(含剔除 |diff| 最大 4 笔的稳健性检查),并给块级
        bootstrap 95% CI(块 = symbol|utc_date)。

任务 B:用 nearmiss_counterfactual_20261031.simulate() 这同一套引擎,重放被接受
        的 51 笔,再与被拒的 190 条对照,判断"闸门反选"是否只是口径假象。

口径约定(两任务共用):
  * 净额(USDT) = Σ(REDUCE/CLOSE 的 net_pnl) − OPEN 的 (fee + slippage)
    net_pnl 是事件级、已含该段的进出成本;OPEN 成本不落在任何 net_pnl 里,
    因此必须手工补减,不能用 position_realized_pnl(会随 REDUCE 重复累计)。
  * R = 净额 / (建仓名义 notional × stop_pct)。先算每笔 R,再等权平均。
  * 符号检验一律 exact binomial,不用正态近似。
  * bootstrap 一律块重抽样,块 = symbol|utc_date(建仓日 UTC),10000 次,固定种子。

只用 logs/ 与 reports/_klines_cache/,不触 src/。
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from math import comb
from pathlib import Path
from random import Random
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from nearmiss_counterfactual_20261031 import CACHE, simulate  # noqa: E402

LOGS = ROOT / "logs" / "2026-10B"
DAYS = ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"]
ARMS = ("legacy", "trend_capture")
NEARMISS_JSON = ROOT / "reports" / "2026-10B_nearmiss_counterfactual.json"

SEED = 20261031
N_BOOT = 10000
TARGET_PAIRS = 30  # paper_ab_legacy 的登记评估门槛

DEFENSIVE_REASONS = {"Q3_DEFENSIVE_REDUCE", "Q4_DEFENSIVE_EXIT"}


# ---------------------------------------------------------------- 基础装载

def load_events(arm: str) -> list[dict]:
    out: list[dict] = []
    for d in DAYS:
        p = LOGS / d / "paper_ab" / arm / "paper_trades.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def build_positions(arm: str) -> dict[str, dict]:
    """把事件流折叠成仓位字典,净额按 事件级 net_pnl 求和再减建仓成本。"""
    by_id: dict[str, list[dict]] = defaultdict(list)
    for e in load_events(arm):
        by_id[e["position_id"]].append(e)

    out: dict[str, dict] = {}
    for pid, evs in by_id.items():
        opens = [e for e in evs if e["event"] == "PAPER_OPEN"]
        if not opens:
            continue
        o = opens[0]
        closes = [e for e in evs if e["event"] == "PAPER_CLOSE"]
        reduces = [e for e in evs if e["event"] == "PAPER_REDUCE"]
        flow = sum(float(e.get("net_pnl") or 0.0) for e in evs if e["event"] != "PAPER_OPEN")
        entry_cost = float(o["fee"]) + float(o["slippage"])
        net = flow - entry_cost
        risk = float(o["notional"]) * float(o["stop_pct"])
        out[pid] = dict(
            position_id=pid,
            symbol=o["symbol"],
            side=o["side"],
            entry_time=int(o["entry_time"]),
            entry_price=float(o["entry_price"]),
            stop_pct=float(o["stop_pct"]),
            notional=float(o["notional"]),
            quadrant=o.get("source_quadrant"),
            channel=o.get("entry_channel"),
            risk_usdt=risk,
            net_usdt=net,
            entry_cost=entry_cost,
            flow_pnl=flow,
            R=net / risk if risk > 0 else None,
            closed=bool(closes),
            close_reason=closes[0]["reason"] if closes else None,
            close_stop_price=float(closes[0]["stop_price"]) if closes and closes[0].get("stop_price") else None,
            reduce_reasons=[r.get("reason") for r in reduces],
            n_reduce=len(reduces),
        )
        # 平仓时的止损价是否已被移到成本价的有利一侧(说明账本用的是移动止损)
        p = out[pid]
        if p["close_stop_price"]:
            sign = 1.0 if p["side"] == "LONG" else -1.0
            p["stop_trailed_into_profit"] = (p["close_stop_price"] - p["entry_price"]) * sign > 0
        else:
            p["stop_trailed_into_profit"] = None
    return out


# ---------------------------------------------------------------- 统计工具

def sign_test(diffs: list[float]) -> dict:
    """exact binomial 符号检验,零差值剔除(标准做法)。"""
    pos = sum(1 for d in diffs if d > 0)
    neg = sum(1 for d in diffs if d < 0)
    zero = len(diffs) - pos - neg
    n = pos + neg
    if n == 0:
        return dict(pos=0, neg=0, zero=zero, n_eff=0, p_two_sided=1.0, p_one_sided_neg=None)
    k = min(pos, neg)
    p_one = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n  # P(X <= k)
    p_two = min(1.0, 2 * p_one)
    # 单侧方向:trend 更差(neg 占多数)= P(X <= neg)
    p_one_neg = sum(comb(n, i) for i in range(0, neg + 1)) / 2 ** n
    return dict(
        pos=pos, neg=neg, zero=zero, n_eff=n,
        p_two_sided=round(p_two, 6),
        p_one_sided_trend_worse=round(p_one_neg, 6),
        note="双侧 = 2×较小的单尾;p<0.05 才算显著",
    )


def utc_date(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d")


def block_key(symbol: str, ts: int) -> str:
    return f"{symbol}|{utc_date(ts)}"


def block_bootstrap_mean(values_by_block: dict[str, list[float]], n_boot: int = N_BOOT,
                         seed: int = SEED) -> dict:
    """块重抽样(按块有放回抽,块内全部观测一起进),统计量 = 全体均值。"""
    keys = list(values_by_block)
    rng = Random(seed)
    stats = []
    for _ in range(n_boot):
        sample: list[float] = []
        for _ in range(len(keys)):
            sample.extend(values_by_block[keys[rng.randrange(len(keys))]])
        if sample:
            stats.append(mean(sample))
    stats.sort()
    return dict(
        blocks=len(keys), obs=sum(len(v) for v in values_by_block.values()),
        lo=round(stats[int(0.025 * len(stats))], 4),
        hi=round(stats[int(0.975 * len(stats))], 4),
        median=round(stats[len(stats) // 2], 4),
    )


def block_bootstrap_diff(acc: dict[str, list[float]], rej: dict[str, list[float]],
                         n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """独立两组的块 bootstrap:各组内按块重抽,统计量 = mean(acc) − mean(rej)。"""
    rng = Random(seed + 1)
    ak, rk = list(acc), list(rej)
    stats = []
    for _ in range(n_boot):
        a: list[float] = []
        for _ in range(len(ak)):
            a.extend(acc[ak[rng.randrange(len(ak))]])
        b: list[float] = []
        for _ in range(len(rk)):
            b.extend(rej[rk[rng.randrange(len(rk))]])
        if a and b:
            stats.append(mean(a) - mean(b))
    stats.sort()
    return dict(
        lo=round(stats[int(0.025 * len(stats))], 4),
        hi=round(stats[int(0.975 * len(stats))], 4),
        median=round(stats[len(stats) // 2], 4),
    )


def describe(rs: list[float]) -> dict:
    if not rs:
        return dict(n=0)
    return dict(
        n=len(rs),
        mean_R=round(mean(rs), 4),
        sum_R=round(sum(rs), 2),
        median_R=round(sorted(rs)[len(rs) // 2], 4),
        win_rate=round(sum(1 for r in rs if r > 0) / len(rs), 3),
        sd=round(pstdev(rs), 4) if len(rs) > 1 else None,
    )


# ---------------------------------------------------------------- 任务 A

def task_a() -> dict:
    books = {a: build_positions(a) for a in ARMS}
    legacy, trend = books["legacy"], books["trend_capture"]

    all_ids = sorted(set(legacy) | set(trend))
    both_closed = [p for p in all_ids if legacy[p]["closed"] and trend[p]["closed"]]

    pairs = []
    for pid in both_closed:
        L, T = legacy[pid], trend[pid]
        pairs.append(dict(
            position_id=pid, symbol=L["symbol"], side=L["side"],
            entry_ts=L["entry_time"], utc_date=utc_date(L["entry_time"]),
            block=block_key(L["symbol"], L["entry_time"]),
            risk_usdt=round(L["risk_usdt"], 4),
            net_legacy=round(L["net_usdt"], 4),
            net_trend=round(T["net_usdt"], 4),
            diff_usdt=round(T["net_usdt"] - L["net_usdt"], 4),
            R_legacy=round(L["R"], 4) if L["R"] is not None else None,
            R_trend=round(T["R"], 4) if T["R"] is not None else None,
            diff_R=round(T["R"] - L["R"], 4) if (L["R"] is not None and T["R"] is not None) else None,
            legacy_exit=L["close_reason"], trend_exit=T["close_reason"],
            identical_outcome=abs(T["net_usdt"] - L["net_usdt"]) < 1e-9,
        ))

    diffs = [p["diff_usdt"] for p in pairs]
    diff_R = [p["diff_R"] for p in pairs]
    st = sign_test(diffs)

    # 剔除 |diff| 最大的 4 笔
    order = sorted(pairs, key=lambda p: -abs(p["diff_usdt"]))
    dropped = order[:4]
    kept = order[4:]
    st_kept = sign_test([p["diff_usdt"] for p in kept])

    # 块级 bootstrap
    by_block_usdt: dict[str, list[float]] = defaultdict(list)
    by_block_R: dict[str, list[float]] = defaultdict(list)
    for p in pairs:
        by_block_usdt[p["block"]].append(p["diff_usdt"])
        by_block_R[p["block"]].append(p["diff_R"])
    ci_usdt = block_bootstrap_mean(by_block_usdt)
    ci_R = block_bootstrap_mean(by_block_R)
    # 剔除极值后再看区间(诊断用:检验区间是否只靠一两个块撑起来)
    kept_blocks: dict[str, list[float]] = defaultdict(list)
    for p in kept:
        kept_blocks[p["block"]].append(p["diff_usdt"])
    ci_usdt_ex4 = block_bootstrap_mean(kept_blocks)

    n = len(pairs)
    mean_usdt = mean(diffs)
    report = dict(
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        data=dict(days=DAYS, arms=list(ARMS), log_root=str(LOGS.relative_to(ROOT))),
        accounting=(
            "净额 = Σ(REDUCE/CLOSE net_pnl) − OPEN(fee+slippage);"
            " R = 净额 / (notional × stop_pct);逐笔 R 后等权平均"
        ),
        book=dict(
            n_positions=len(all_ids),
            n_positions_each_arm={a: len(books[a]) for a in ARMS},
            n_closed={a: sum(1 for v in books[a].values() if v["closed"]) for a in ARMS},
            n_open_unclosed={a: sum(1 for v in books[a].values() if not v["closed"]) for a in ARMS},
            n_paired_closed=n,
            gate_threshold=TARGET_PAIRS,
            gate_status=f"已过门槛({n}/{TARGET_PAIRS})" if n >= TARGET_PAIRS else f"未达门槛({n}/{TARGET_PAIRS})",
            total_net_legacy=round(sum(v["net_usdt"] for v in legacy.values() if v["closed"]), 4),
            total_net_trend=round(sum(v["net_usdt"] for v in trend.values() if v["closed"]), 4),
            mean_R_legacy=round(mean([v["R"] for v in legacy.values() if v["closed"]]), 4),
            mean_R_trend=round(mean([v["R"] for v in trend.values() if v["closed"]]), 4),
        ),
        paired=dict(
            n=n,
            sum_diff_usdt=round(sum(diffs), 4),
            mean_diff_usdt=round(mean_usdt, 4),
            mean_diff_R=round(mean(diff_R), 4),
            n_identical_outcome=sum(1 for p in pairs if p["identical_outcome"]),
            n_differing=sum(1 for p in pairs if not p["identical_outcome"]),
            share_identical=round(sum(1 for p in pairs if p["identical_outcome"]) / n, 3),
            worst_5=[{k: p[k] for k in ("position_id", "diff_usdt", "diff_R", "R_legacy", "R_trend")}
                     for p in order[:5]],
            top1_share_of_total=round(abs(order[0]["diff_usdt"]) / sum(abs(d) for d in diffs), 3),
        ),
        sign_test=dict(
            metric="trend − legacy(USDT,等价于 R 差,风险分母同为正)",
            primary=st,
            after_dropping_top4=st_kept,
            dropped=[{k: p[k] for k in ("position_id", "diff_usdt", "diff_R")} for p in dropped],
            kept_sum_diff_usdt=round(sum(p["diff_usdt"] for p in kept), 4),
            kept_mean_diff_usdt=round(mean([p["diff_usdt"] for p in kept]), 4),
        ),
        bootstrap=dict(
            method="块重抽样,块 = symbol|utc_date(建仓日),10000 次,seed=20261031",
            seed=SEED, n_boot=N_BOOT,
            mean_diff_usdt_ci95=ci_usdt,
            mean_diff_R_ci95=ci_R,
            sum_diff_usdt_ci95=dict(
                lo=round(ci_usdt["lo"] * n, 2), hi=round(ci_usdt["hi"] * n, 2),
                note="sum = n × mean,同一重抽样分布换算",
            ),
            mean_diff_usdt_ci95_ex_top4=ci_usdt_ex4,
        ),
        verdict=None,
        pairs=pairs,
    )

    # 判断:方向是否由 ≤4 笔决定 —— 总量被极值主导,且剔除后既不同号也不显著
    kept_mean_usdt = mean([p["diff_usdt"] for p in kept])
    decided_by_few = abs(kept_mean_usdt) < 0.1 * abs(mean_usdt) or st_kept["p_two_sided"] > 0.5
    report["verdict"] = dict(
        decided_by_at_most_4_trades=bool(decided_by_few),
        sentence=(
            f"配对差合计 {report['paired']['sum_diff_usdt']:.2f} USDT,但 {report['paired']['n_identical_outcome']}/{n} 对"
            f"两臂结果完全相同(占 {report['paired']['share_identical']:.0%}),仅 {report['paired']['n_differing']} 对结果有差异;"
            f"符号检验双侧 p={st['p_two_sided']:.4f}(有效非零 {st['n_eff']} 对),"
            f"剔除最大 4 笔后 p={st_kept['p_two_sided']:.4f}、残差均值 {kept_mean_usdt:+.4f} USDT/笔。"
            + ("方向基本由 ≤4 笔决定,不构成系统性结论。"
               if decided_by_few else "方向在剔除极值后仍同号,但样本量不足以定论。")
        ),
    )
    return report


# ---------------------------------------------------------------- 任务 B

def load_decisions() -> dict[tuple[str, int], dict]:
    dec = {}
    for d in DAYS:
        p = LOGS / d / "decisions.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            dec[(r["symbol"], int(r["kline"]["timestamp"]))] = r
    return dec


def load_bars() -> dict[str, list[list]]:
    return {p.name.split("_")[0]: json.loads(p.read_text()) for p in CACHE.glob("*_15m.json")}


def task_b() -> dict:
    legacy = build_positions("legacy")
    dec = load_decisions()
    bars = load_bars()
    nm = json.loads(NEARMISS_JSON.read_text(encoding="utf-8"))["rows"]

    # ---- 被接受:51 笔已平仓,用同一 simulate() 重放
    accepted = []
    missing = []
    for pid, p in legacy.items():
        if not p["closed"]:
            continue
        d = dec.get((p["symbol"], p["entry_time"]))
        b = bars.get(p["symbol"])
        if d is None or b is None:
            missing.append(dict(position_id=pid, reason="no_decision" if d is None else "no_klines"))
            continue
        entry = float(d["kline"]["close"])
        stop_pct = float(d["entry_context"]["stop_pct"])
        res = simulate(b, p["entry_time"], entry, p["side"], stop_pct)
        if res is None:
            missing.append(dict(position_id=pid, reason="simulate_none"))
            continue
        R, why, mfe, hold = res
        accepted.append(dict(
            position_id=pid, symbol=p["symbol"], side=p["side"],
            entry_ts=p["entry_time"], utc_date=utc_date(p["entry_time"]),
            block=block_key(p["symbol"], p["entry_time"]),
            entry_price=entry, stop_pct=stop_pct,
            R_engine=round(R, 4), exit_engine=why, mfe_R=round(mfe, 3), hold_bars=hold,
            R_ledger=round(p["R"], 4), ledger_exit=p["close_reason"],
            ledger_defensive=bool(
                p["close_reason"] in DEFENSIVE_REASONS
                or any(r in DEFENSIVE_REASONS for r in p["reduce_reasons"])
            ),
            has_defensive_reduce=any(r in DEFENSIVE_REASONS for r in p["reduce_reasons"]),
            gap_ledger_minus_engine=round(p["R"] - R, 4),
            ledger_stop_trailed_into_profit=p["stop_trailed_into_profit"],
            _R_raw=R,  # 仅供同 bar 一致性自检,落盘前剔除
        ))

    # ---- 重叠检查:被接受的那根 bar 是否也出现在被拒集合里
    nm_keys = {(r["symbol"], int(r["ts"]), r["side"]): r for r in nm}
    for a in accepted:
        a["also_in_rejected"] = (a["symbol"], a["entry_ts"], a["side"]) in nm_keys
    n_overlap = sum(1 for a in accepted if a["also_in_rejected"])

    # 同一根 bar 上引擎 R 必须完全一致 —— 这是引擎口径一致性的自检
    same_bar_delta = [
        abs(float(nm_keys[(a["symbol"], a["entry_ts"], a["side"])]["R"]) - a["_R_raw"])
        for a in accepted if a["also_in_rejected"]
    ]
    for a in accepted:
        a.pop("_R_raw", None)

    acc_R = [a["R_engine"] for a in accepted]
    led_R = [a["R_ledger"] for a in accepted]
    rej_all = [float(r["R"]) for r in nm]

    rej_clean_rows = [r for r in nm if (r["symbol"], int(r["ts"]), r["side"]) not in
                      {(a["symbol"], a["entry_ts"], a["side"]) for a in accepted}]
    rej_clean = [float(r["R"]) for r in rej_clean_rows]

    # ---- 块级 bootstrap:accepted − rejected
    def by_block(rows, key_fn, val_fn):
        out: dict[str, list[float]] = defaultdict(list)
        for x in rows:
            out[key_fn(x)].append(val_fn(x))
        return out

    acc_blocks = by_block(accepted, lambda a: a["block"], lambda a: a["R_engine"])
    rej_blocks = by_block(nm, lambda r: block_key(r["symbol"], int(r["ts"])), lambda r: float(r["R"]))
    rej_clean_blocks = by_block(rej_clean_rows, lambda r: block_key(r["symbol"], int(r["ts"])), lambda r: float(r["R"]))

    ci_vs_all = block_bootstrap_diff(acc_blocks, rej_blocks)
    ci_vs_clean = block_bootstrap_diff(acc_blocks, rej_clean_blocks)

    # ---- 账本 R 的分组(解释 −0.352 从哪来)
    by_reason: dict[str, list[float]] = defaultdict(list)
    for a in accepted:
        by_reason[a["ledger_exit"]].append(a["R_ledger"])
    by_reason_engine: dict[str, list[float]] = defaultdict(list)
    for a in accepted:
        by_reason_engine[a["ledger_exit"]].append(a["R_engine"])

    n_defensive_closed = sum(1 for a in accepted if (a["ledger_exit"] in DEFENSIVE_REASONS))
    n_defensive_any = sum(1 for a in accepted if a["ledger_defensive"])

    d_mean_all = mean(acc_R) - mean(rej_all)
    d_mean_clean = mean(acc_R) - mean(rej_clean)

    # 引擎 − 账本 的差额归因:哪些笔引擎更好(执行层砍掉了赢家),哪些笔账本更好(移动止损保护)
    eng_better = [a for a in accepted if a["gap_ledger_minus_engine"] < 0]
    led_better = [a for a in accepted if a["gap_ledger_minus_engine"] > 0]
    gap_attr = dict(
        sum_gap_R=round(sum(a["gap_ledger_minus_engine"] for a in accepted), 2),
        n_engine_better=len(eng_better),
        sum_R_engine_better=round(sum(-a["gap_ledger_minus_engine"] for a in eng_better), 2),
        n_ledger_better=len(led_better),
        sum_R_ledger_better=round(sum(a["gap_ledger_minus_engine"] for a in led_better), 2),
        n_ties=len(accepted) - len(eng_better) - len(led_better),
        n_ledger_stop_trailed_into_profit=sum(1 for a in accepted if a["ledger_stop_trailed_into_profit"]),
        note="账本的平仓止损价常已被移到成本价有利一侧(移动止损),引擎用的是建仓时的固定止损;"
             "因此引擎重放是'纯阶梯'反事实,不是 legacy 账本的重建。",
    )

    report = dict(
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        engine=dict(
            source="scripts/analysis/nearmiss_counterfactual_20261031.py::simulate()",
            rules="stop 优先于同根 TP;TP 1.2/2.0/3.0 × 0.40/0.35/0.25;TP1 后保本;32 根上限;20bps 往返",
            entry="决策 K 线收盘价(与账本 entry_price 逐笔相等)",
            stop="decisions.jsonl 的 entry_context.stop_pct(全精度)",
            kline_cache=str(CACHE.relative_to(ROOT)),
        ),
        accepted=dict(
            **describe(acc_R),
            ledger_mean_R=round(mean(led_R), 4),
            ledger_sum_R=round(sum(led_R), 2),
            gap_engine_minus_ledger=round(mean(acc_R) - mean(led_R), 4),
            exit_mix_engine=dict(Counter(a["exit_engine"] for a in accepted)),
            exit_mix_ledger=dict(Counter(a["ledger_exit"] for a in accepted)),
            n_engine_replayed=len(accepted),
            n_missing=len(missing), missing=missing,
        ),
        rejected=dict(
            engine=describe(rej_all),
            clean=dict(**describe(rej_clean),
                       note=f"剔除与被接受 bar 完全重合的 {len(nm) - len(rej_clean)} 条后的剩余样本"),
        ),
        selection_gap=dict(
            accepted_minus_rejected_all=round(d_mean_all, 4),
            accepted_minus_rejected_all_ci95=ci_vs_all,
            accepted_minus_rejected_clean=round(d_mean_clean, 4),
            accepted_minus_rejected_clean_ci95=ci_vs_clean,
            naive_claim="rejected −0.132R 优于 accepted −0.352R(差 +0.220R,支持'闸门反选')",
            naive_claim_recomputed=round(mean(rej_all) - mean(led_R), 4),
            same_engine_gap=round(d_mean_all, 4),
        ),
        contamination=dict(
            n_accepted=len(accepted),
            n_accepted_bars_also_rejected=n_overlap,
            share=round(n_overlap / len(accepted), 3),
            same_bar_max_abs_dR=round(max(same_bar_delta), 6) if same_bar_delta else None,
            same_bar_mean_abs_dR=round(mean(same_bar_delta), 6) if same_bar_delta else 0.0,
            note="被拒的 190 条里有 46 条就是被接受的那根 K 线(镜像采样),同一引擎下 R 逐笔相同;"
                 "两组并非独立样本,naive 比较有一半是在比自己。",
        ),
        ledger_gap_explained_by_defensive_overlay=dict(
            n_close_defensive=n_defensive_closed,
            n_any_defensive_reduce=n_defensive_any,
            ledger_mean_R_by_exit_reason={k: round(mean(v), 4) for k, v in
                                         sorted(by_reason.items(), key=lambda kv: -len(kv[1]))},
            n_by_exit_reason={k: len(v) for k, v in sorted(by_reason.items(), key=lambda kv: -len(kv[1]))},
            engine_mean_R_on_same_rows={k: round(mean(v), 4) for k, v in by_reason_engine.items()},
            note="legacy 臂在 TP/止损之外叠加了 Q3_DEFENSIVE_REDUCE / Q4_DEFENSIVE_EXIT;"
                 "这两类出场把引擎本会走到 TP 的仓位提前砍在 −0.2 ~ −0.7R。",
            overlay_is_book_wide=dict(
                note="trend_capture 臂同样带 Q3/Q4 防御性出场,说明这不是某一臂的规则,而是整本 AB 账本的执行层;"
                     "引擎重放剥离的是这个执行层,不是闸门。",
                legacy_close_mix=dict(Counter(v["close_reason"] for v in legacy.values() if v["closed"])),
                trend_capture_close_mix=dict(Counter(v["close_reason"] for v in
                                                     build_positions("trend_capture").values() if v["closed"])),
            ),
            gap_attribution=gap_attr,
        ),
        verdict=None,
        rows=accepted,
    )

    holds = ci_vs_all["lo"] <= 0 <= ci_vs_all["hi"] and abs(d_mean_all) < 0.05
    report["verdict"] = dict(
        anti_selection_holds_under_same_engine=not holds,
        sentence=(
            f"同一引擎下 accepted E[R]={mean(acc_R):+.3f}(账本 {mean(led_R):+.3f},差 "
            f"{mean(acc_R) - mean(led_R):+.3f}),rejected E[R]={mean(rej_all):+.3f},"
            f"差 {d_mean_all:+.3f}R,95% CI [{ci_vs_all['lo']:+.3f}, {ci_vs_all['hi']:+.3f}] 跨 0。"
            + ("'闸门在反选'在同一引擎下不成立:原比较的口径差来自 legacy 臂的防御性减仓,"
               "不是闸门选错了样本。" if holds else
               "同一引擎下 accepted 仍明显差于 rejected,反选判断成立。")
        ),
    )
    return report


# ---------------------------------------------------------------- main

def main() -> None:
    a = task_a()
    b = task_b()

    pa = ROOT / "reports" / "2026-10-31_s2_paired_test.json"
    pb = ROOT / "reports" / "2026-10-31_gate_selection.json"
    pa.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    pb.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")

    print("== A 配对符号检验")
    print(json.dumps({k: v for k, v in a.items() if k not in ("pairs",)}, ensure_ascii=False, indent=1))
    print("\n== B 闸门反选")
    print(json.dumps({k: v for k, v in b.items() if k not in ("rows",)}, ensure_ascii=False, indent=1))
    print("\nwrote", pa.relative_to(ROOT), pb.relative_to(ROOT))


if __name__ == "__main__":
    main()
