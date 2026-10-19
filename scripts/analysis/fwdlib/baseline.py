"""逐条配对安慰剂基线。

为什么不用「按块随机抽决策」
--------------------------
旧做法按 ``(symbol, date)`` 分块,每块随机抽 ≤20 条决策,直接拿这些决策的
``R`` 当基线。问题在于**成本构成不一致**:基线样本的 ``stop_pct`` 分布与总体
不同,而 ``cost_R = bps/1e4/stop_pct`` 对止损宽度极其敏感,于是基线的平均
``cost_R`` 与总体差出约 0.08R —— 这一点差异足以让「每个分数档 lift 都为负」
这类结论完全来自成本口径而非信号。

本模块改为**逐条配对**:每条决策配 ``draws`` 条「同 symbol、同 UTC 日、
同 side、同 ``stop_pct``、随机 bar」的对照。止损宽度相同 ⇒ 成本项逐条抵消 ⇒
``delta_R`` 与 ``delta_R_net`` 在 barrier 口径下恒等(见 ``lift_summary`` 的
``identity_max_abs_diff``)。

采样可复现性
------------
每条决策的 RNG 由 ``sha1("{seed}|{symbol}|{ts}|{side}")`` 派生,与遍历顺序、
并发切分方式无关;不使用全局 ``random``。同 seed 重跑逐行一致。

局限性
------
安慰剂只排除决策自身所在的那根 bar,**不做邻域排除**:对照的 32 根前向窗口
完全可能与真实样本的窗口重叠。因此安慰剂**不是完全独立的对照**,只用于
抵消成本构成差异,不能当作「独立随机样本」做显著性推断。
"""

from __future__ import annotations

import hashlib
import math
import random
import statistics
from datetime import date, datetime, timezone

from .config import LabelConfig
from .cost import cost_r
from .labeler import label_barrier
from .stats import block_bootstrap_mean

__all__ = ["lift_summary", "matched_placebo", "placebo_pool"]

_SECONDS_PER_DAY = 86_400


# --------------------------------------------------------------------------- #
# 日期与随机种子
# --------------------------------------------------------------------------- #

def _day_index(value) -> int:
    """把 UTC 日期(``"YYYY-MM-DD"`` / ``date`` / ``datetime``)转成 epoch 日序号。"""
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    elif isinstance(value, str):
        dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        raise TypeError(f"date 必须是 'YYYY-MM-DD' 字符串或 date/datetime, 实际 {value!r}")
    return int(dt.timestamp()) // _SECONDS_PER_DAY


def _utc_day(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _rng_for(seed: int, symbol: str, ts: int, side: str) -> random.Random:
    """每条决策独立的 RNG:前 8 字节大端转 int 作种子。"""
    digest = hashlib.sha1(f"{seed}|{symbol}|{ts}|{side}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


# --------------------------------------------------------------------------- #
# 对照池
# --------------------------------------------------------------------------- #

def placebo_pool(bars, per_symbol, index, symbol, date, *, exclude_ts=None) -> list[int]:
    """返回 ``(symbol, UTC 日)`` 下全部 bar 时间戳(升序),``exclude_ts`` 时剔除该根。

    ``bars`` / ``index`` 只为与 :mod:`fwdlib.labeler` 的调用约定保持一致而保留,
    池子由 ``per_symbol``(升序时间戳列表)直接筛出。

    池子**只排除决策自身那根 bar**,不排除邻域:对照的 32 根前向窗口允许与真实
    样本重叠,因此安慰剂不是完全独立的对照。
    """
    if symbol not in per_symbol:
        return []
    target = _day_index(date)
    exclude = exclude_ts
    return [
        ts for ts in per_symbol[symbol]
        if ts // _SECONDS_PER_DAY == target and ts != exclude
    ]


# --------------------------------------------------------------------------- #
# 逐条配对
# --------------------------------------------------------------------------- #

def _invalid_row(keep_sd: bool) -> dict:
    """无有效对照的行:均值置 ``nan``,两条 delta 置 0 且 ``placebo_valid=False``。

    delta 不用 ``nan`` 是为了不污染批量聚合:``max()`` 遇到 ``nan`` 会直接返回
    ``nan``(取决于出现顺序),``fmean`` 也会被带偏。置 0 表示「本行没有 lift
    估计」,**下游必须用 ``placebo_valid`` 过滤后再统计**。
    """
    nan = float("nan")
    row = {"placebo_R_mean": nan}
    if keep_sd:
        row["placebo_R_sd"] = nan
    row.update({
        "placebo_n_valid": 0,
        "placebo_valid": False,
        "delta_R": 0.0,
        "delta_R_net": 0.0,
    })
    return row


def _placebo_sd(values: list[float]) -> float:
    if len(values) >= 2:
        return statistics.stdev(values)
    if len(values) == 1:
        return 0.0
    return float("nan")


def matched_placebo(labeled, bars, per_symbol, index, *,
                    draws=20, seed=7, entry_mode="next_open", horizon=32,
                    cfg=None, max_retry=8, keep_sd=True) -> list[dict]:
    """为每条已标注决策配 ``draws`` 条同质安慰剂,返回逐行配对差。

    参数
    ----
    labeled
        :func:`fwdlib.labeler.run_labeling` 的输出行,需含 ``symbol`` / ``ts`` /
        ``side`` / ``stop_pct_eff``(或 ``stop_pct``)/ ``date`` / ``R`` /
        ``R_net``;``atr_pct`` 可选。输出与输入**逐行同序**。
    draws
        每条决策的有效对照目标数;单次 draw 抽到的 bar 若标注失败
        (``label_barrier`` 返回 ``None``,通常是样本尾部不足 32 根),最多
        **重试 ``max_retry`` 次**(即单 draw 最多尝试 ``max_retry + 1`` 次),
        仍失败则该 draw 不计入。
    keep_sd
        是否输出 ``placebo_R_sd``(大批量跑时可关掉省内存)。

    每行返回 ``placebo_R_mean`` / ``placebo_R_sd`` / ``placebo_n_valid`` /
    ``placebo_valid`` / ``delta_R`` / ``delta_R_net``。无有效 draw 时均值为
    ``nan``、``placebo_valid=False``,两条 delta 置 0(见 :func:`_invalid_row`),
    统计前须按 ``placebo_valid`` 过滤。

    ``delta_R_net`` 用 ``cost_r(cfg.cost_bps, stop_pct_eff)`` 折算;由于安慰剂与
    真样本止损宽度相同,成本逐条抵消,barrier 口径下 ``delta_R == delta_R_net``。

    抽样只排除决策自身那根 bar,允许与前向 32 根窗口重叠 —— 安慰剂不是完全
    独立的对照,只用于消除成本构成偏差。
    """
    c = LabelConfig() if cfg is None else cfg
    out: list[dict] = []
    for row in labeled:
        symbol = row["symbol"]
        ts = row["ts"]
        side = row["side"]
        stop = row.get("stop_pct_eff")
        if stop is None:
            stop = row.get("stop_pct")
        if draws <= 0 or not stop or stop <= 0:
            out.append(_invalid_row(keep_sd))
            continue

        day = row.get("date") or _utc_day(ts)
        pool = placebo_pool(bars, per_symbol, index, symbol, day, exclude_ts=ts)
        if not pool:
            out.append(_invalid_row(keep_sd))
            continue

        rng = _rng_for(seed, symbol, ts, side)
        values: list[float] = []
        for _ in range(draws):
            res = None
            for _attempt in range(max_retry + 1):
                pick = pool[rng.randrange(len(pool))]
                fake = {
                    "symbol": symbol,
                    "ts": pick,
                    "side": side,
                    "stop_pct": stop,
                    "atr_pct": row.get("atr_pct"),
                }
                res = label_barrier(bars, per_symbol, index, fake, stop, entry_mode,
                                    cfg=c, horizon=horizon)
                if res is not None:
                    break
            if res is not None:
                values.append(res["R"])

        if not values:
            out.append(_invalid_row(keep_sd))
            continue

        mean = statistics.fmean(values)
        cost = cost_r(c.cost_bps, stop)
        item = {"placebo_R_mean": mean}
        if keep_sd:
            item["placebo_R_sd"] = _placebo_sd(values)
        item.update({
            "placebo_n_valid": len(values),
            "placebo_valid": True,
            "delta_R": row["R"] - mean,
            "delta_R_net": row["R_net"] - (mean - cost),
        })
        out.append(item)
    return out


# --------------------------------------------------------------------------- #
# 分档 lift
# --------------------------------------------------------------------------- #

def _is_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _lift_values(row) -> tuple[float, float] | None:
    """取 (lift_gross, lift_net);安慰剂无效或缺 ``R`` 时返回 ``None``。"""
    placebo = row.get("placebo_R_mean")
    if not _is_number(placebo):
        return None
    r = row.get("R")
    if not _is_number(r):
        return None

    gross = row.get("delta_R")
    if not _is_number(gross):
        gross = r - placebo

    net = row.get("delta_R_net")
    if not _is_number(net):
        r_net = row.get("R_net")
        if not _is_number(r_net):
            net = gross
        else:
            cost = row.get("cost_r")
            if not _is_number(cost):
                cost = r - r_net
            net = r_net - (placebo - cost)
    return float(gross), float(net)


def _bucket_label(lo: float, hi: float) -> str:
    if hi >= 1e9:
        return f">={lo:g}"
    if lo <= 0:
        return f"<{hi:g}"
    return f"{lo:g}-{hi:g}"


def lift_summary(rows, *, block_key="block", iters=2000, seed=7,
                 score_buckets=((92, 1e9), (82, 92), (78, 82), (68, 78), (0, 68))) -> dict:
    """按分数档汇总配对 lift,并用块 bootstrap 给出 80% 区间。

    每个统计单元返回 ``n``(该单元全部行数)/ ``n_valid``(安慰剂有效行数)/
    ``E_R`` / ``E_R_placebo`` / ``lift_gross`` / ``lift_gross_ci80`` /
    ``lift_net`` / ``lift_net_ci80``。``E_R`` 与 ``E_R_placebo`` 用同一批有效行,
    差值即逐行 lift 的均值。区间来自
    :func:`fwdlib.stats.block_bootstrap_mean`(按 ``block_key`` 分块、旧口径);
    块数 < 5 时返回 ``None``。

    ``by_score`` 恒按传入的 ``score_buckets`` 顺序输出全部桶(空桶 ``n=0``、
    统计量为 ``None``);无法落桶的行(缺 ``score`` 或越界)计入
    ``overall["n_unbucketed"]``,不进入任何桶。

    ``identity_max_abs_diff`` = 全体逐行 ``max|delta_R - delta_R_net|``(只统计
    两者都有限的行)。barrier 口径下应 ~0;ladder 口径下 ``R`` 已含成本、
    该值不为 0,属预期。
    """
    rows = list(rows)

    def _summarize(subset) -> dict:
        pairs = []
        for row in subset:
            values = _lift_values(row)
            if values is not None:
                pairs.append((row, values))
        gross = [v[0] for _r, v in pairs]
        net = [v[1] for _r, v in pairs]
        e_r = [row["R"] for row, _v in pairs]
        e_p = [row["placebo_R_mean"] for row, _v in pairs]

        by_block_gross: dict = {}
        by_block_net: dict = {}
        for row, (g, n) in pairs:
            key = row.get(block_key)
            by_block_gross.setdefault(key, []).append(g)
            by_block_net.setdefault(key, []).append(n)

        return {
            "n": len(subset),
            "n_valid": len(pairs),
            "E_R": statistics.fmean(e_r) if e_r else None,
            "E_R_placebo": statistics.fmean(e_p) if e_p else None,
            "lift_gross": statistics.fmean(gross) if gross else None,
            "lift_gross_ci80": block_bootstrap_mean(by_block_gross, iters=iters, seed=seed),
            "lift_net": statistics.fmean(net) if net else None,
            "lift_net_ci80": block_bootstrap_mean(by_block_net, iters=iters, seed=seed),
        }

    overall = _summarize(rows)

    buckets = []
    bucketed = 0
    for lo, hi in score_buckets:
        subset = []
        for row in rows:
            score = row.get("score")
            if _is_number(score) and lo <= score < hi:
                subset.append(row)
        bucketed += len(subset)
        entry = {"bucket": _bucket_label(lo, hi)}
        entry.update(_summarize(subset))
        buckets.append(entry)

    overall["n_unbucketed"] = len(rows) - bucketed

    diffs = []
    for row in rows:
        d = row.get("delta_R")
        dn = row.get("delta_R_net")
        if _is_number(d) and _is_number(dn):
            diffs.append(abs(d - dn))

    return {
        "overall": overall,
        "by_score": buckets,
        "identity_max_abs_diff": max(diffs) if diffs else 0.0,
    }
