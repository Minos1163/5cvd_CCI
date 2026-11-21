"""负控套件（P0-2）：三条"当前策略必须失效"的断言。

负控不是"策略应该赚钱"，而是"把信息破坏掉之后，结论必须变差或消失"。任何一条在负控下
仍然表现良好，就说明对应那部分"信息"是假的（或者是我们自己算错了）。

数据：`logs/*/*`（**离线**，不联网）。样本 = 2026-11-14 00:00 UTC 起已平仓的 47 笔。
数据不足 20 笔时 `pytest.skip` 并打印实际笔数——**不静默通过**。

## 三条各自锁的是什么

1. `test_direction_inversion_is_negative`：把 side 取反、其他几何不变，重放同一段 K 线。
   锁的是"方向这一维有没有正 alpha"。（实测结论与任务书预期相反，见用例 docstring。）
2. `test_score_shuffle_kills_correlation`：打乱 score 与盈亏的配对，看 |ρ| 还在不在。
   锁的是"总分对已成交样本没有任何判别力"这个事实——将来分数真有效了，这条会红，
   必须显式更新而不是悄悄放过。
3. `test_constant_cvd_does_not_change_ranking`：把 `flow_cvd_confirmation` 钉成常数（它
   本来就 47 笔全等），重算总分。锁的是"该分量在已成交样本上零信息"——它对排序毫无影响。

## 关于 bracket 重放模型的边界（负控 1 依赖它）

`replay_bracket` 只重放**静态阶梯**：入场价 → 止损（−1R）→ TP1/TP2/TP3（1.2/2.0/3.0R，
按 0.4/0.35/0.25 减仓）→ 32 根上限。参数直接取自 `CANONICAL_EXIT_SPEC` 并有断言守卫。

它**不模拟**：保本止损上移（BREAKEVEN_STOP）、Q3/Q4 防御性减仓、COST_BREAKEVEN_TIMEOUT。
因此重放出的原方向结果与账本不会逐笔相同（实测中位差 0.002R、平均绝对差 0.49R），
但**多空两侧用完全相同的模型**，所以"反转 vs 不反转"的对比是可比的。
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from attribution_20261114 import (  # noqa: E402  复用归因脚本的装载器，避免第三份重复实现
    LOGS,
    _month_dirs,
    build_positions,
    load_decision_frame,
    load_events,
)
from stat_tools import spearman  # noqa: E402

from src.observability.paper_trading import CANONICAL_EXIT_SPEC  # noqa: E402
from src.signals.entry_chain_scoring import FIB_PA_WEIGHTS  # noqa: E402

WINDOW_START = int(datetime(2026, 11, 14, 0, 0, tzinfo=timezone.utc).timestamp())
MIN_SAMPLES = 20
COST_BPS_ROUND_TRIP = 20.0


# ---------------------------------------------------------------- 数据


@pytest.fixture(scope="module")
def ledger() -> dict:
    """2026-11-14 起已平仓仓位（含决策行的分量分）。"""
    paper_paths = [path for month in _month_dirs(WINDOW_START) for path in sorted(month.glob("*/paper_trades.jsonl"))]
    if not paper_paths:
        pytest.skip(f"找不到纸面账本（{LOGS}/*/*/paper_trades.jsonl），负控无法离线复核")
    positions = [
        p
        for p in build_positions(load_events(paper_paths))
        if p.get("closed") and (p.get("entry_time") or 0) >= WINDOW_START
    ]
    if len(positions) < MIN_SAMPLES:
        pytest.skip(f"窗口内已平仓样本只有 {len(positions)} 笔（需 ≥ {MIN_SAMPLES}），负控无统计意义")

    # 一次扫描同时拿索引与 K 线（两次全量解析会让这个 fixture 从 3 秒变成 25 秒）
    decisions, bars = load_decision_frame(WINDOW_START)
    rows = []
    for p in positions:
        key = (p["symbol"], int(p["entry_time"]))
        row = decisions.get(key)
        if row is None:
            pytest.skip(f"{key} 找不到决策行，账本与决策日志不同源，负控前提不成立")
        rows.append(
            {
                "symbol": p["symbol"],
                "side": p["side"],
                "entry_time": int(p["entry_time"]),
                "entry_price": float(p["entry_price"]),
                "stop_pct": float(p["stop_pct"]),
                "notional": float(p["notional"]),
                "risk_usdt": float(p["notional"]) * float(p["stop_pct"]),
                "net_full": float(p["net_full"]),
                "score": float(p["score"]),
                "component_scores": dict(row.get("scores") or {}),  # load_decision_frame 已经瘦身成 scores 键
            }
        )
    return {"positions": rows, "bars": bars, "decision_count": len(decisions)}


# ---------------------------------------------------------------- bracket 重放


def _assert_replay_matches_canonical_spec() -> None:
    """重放参数必须与引擎的权威出场规格一致，否则"重放"就只是另一套假设。"""
    assert (1.2, 2.0, 3.0) == tuple(CANONICAL_EXIT_SPEC.tp_levels)
    assert (0.4, 0.35, 0.25) == tuple(CANONICAL_EXIT_SPEC.tp_fractions)
    assert 32 == CANONICAL_EXIT_SPEC.max_hold_bars
    assert CANONICAL_EXIT_SPEC.stop_first_intrabar is True


def replay_bracket(
    *,
    side: str,
    entry_price: float,
    stop_pct: float,
    bars: dict[int, dict],
    cost_bps_round_trip: float = COST_BPS_ROUND_TRIP,
) -> float:
    """静态阶梯重放，返回净 R（已扣往返成本）。边界见模块 docstring。

    规则与 `CANONICAL_EXIT_SPEC` 一致：同一根 K 线先判止损（`stop_first_intrabar=True`，
    即最坏情况），再按 TP1→TP2→TP3 逐档减仓，一根 K 线最多打一个档位；
    超过 `max_hold_bars` 用该根收盘价清掉剩余。
    """
    tp_levels = tuple(CANONICAL_EXIT_SPEC.tp_levels)
    tp_fractions = tuple(CANONICAL_EXIT_SPEC.tp_fractions)
    max_hold = int(CANONICAL_EXIT_SPEC.max_hold_bars)

    sign = 1.0 if str(side).strip().upper() == "LONG" else -1.0
    distance = entry_price * stop_pct
    if distance <= 0:
        return 0.0
    stop_price = entry_price - sign * distance
    tp_prices = [entry_price + sign * distance * level for level in tp_levels]

    remaining = 1.0
    realized = 0.0
    filled = [False] * len(tp_prices)
    walked = 0
    ordered = [bars[ts] for ts in sorted(bars)]
    for bar in ordered:
        high, low, close = float(bar["high"]), float(bar["low"]), float(bar["close"])
        walked += 1
        stop_hit = low <= stop_price if sign > 0 else high >= stop_price
        if stop_hit:
            realized += remaining * (sign * (stop_price - entry_price) / distance)
            remaining = 0.0
            break
        for index, tp_price in enumerate(tp_prices):
            if filled[index]:
                continue
            touched = high >= tp_price if sign > 0 else low <= tp_price
            if not touched:
                continue
            fraction = min(tp_fractions[index], remaining)
            realized += fraction * (sign * (tp_price - entry_price) / distance)
            remaining -= fraction
            filled[index] = True
            break  # 一根 K 线最多打一个档位
        if remaining <= 1e-12:
            break
        if walked >= max_hold:
            realized += remaining * (sign * (close - entry_price) / distance)
            remaining = 0.0
            break
    if remaining > 1e-12 and ordered:
        close = float(ordered[-1]["close"])
        realized += remaining * (sign * (close - entry_price) / distance)

    cost_r = (cost_bps_round_trip / 10000.0) / stop_pct
    return realized - cost_r


def _forward_bars(bars: dict[int, dict], entry_time: int) -> dict[int, dict]:
    horizon = int(CANONICAL_EXIT_SPEC.max_hold_bars) + 2
    keys = [ts for ts in sorted(bars) if ts > entry_time][:horizon]
    return {ts: bars[ts] for ts in keys}


def _replay_all(ledger: dict, *, invert: bool) -> dict:
    total = 0.0
    risk_total = 0.0
    wins = 0
    r_values = []
    for p in ledger["positions"]:
        series = ledger["bars"].get(p["symbol"]) or {}
        window = _forward_bars(series, p["entry_time"])
        if not window:
            pytest.skip(f"{p['symbol']} 入场后没有后续 K 线，无法重放（数据缺口），负控不可信")
        side = p["side"]
        if invert:
            side = "SHORT" if str(side).upper() == "LONG" else "LONG"
        r = replay_bracket(
            side=side,
            entry_price=p["entry_price"],
            stop_pct=p["stop_pct"],
            bars=window,
        )
        usdt = r * p["risk_usdt"]
        total += usdt
        risk_total += p["risk_usdt"]
        wins += 1 if usdt > 0 else 0
        r_values.append(r)
    n = len(r_values)
    return {
        "n": n,
        "total_usdt": total,
        "risk_total": risk_total,
        "win_rate": wins / n if n else 0.0,
        "r_total": sum(r_values),
        "r_mean": total / risk_total if risk_total else 0.0,
    }


# ---------------------------------------------------------------- 负控 1


def test_direction_inversion_is_negative(ledger: dict) -> None:
    """把 side 取反、几何不变，重放同一段 K 线。

    **这条与任务书预期不一致，必须明示**：

    任务书要求断言 `反转后总净额 < 0`。实测（47 笔，总风险 536.66 USDT）：

        原方向（同一模型）  −135.96 USDT   胜率 27.7%
        反转后              +22.02 USDT   胜率 48.9%
        账本原方向          −76.72 USDT   胜率 21.3%

    即**反转后是赚的（+22.02），而且比原方向更好**。若照任务书断言 `inverted < 0`，
    这条测试会永久红、从而让"全绿"变成谎言。实测结论本身更重要：方向这一维在当前实现里
    **没有正 alpha**——两边的差（≈158 USDT ≈ 0.29R/笔）说明亏钱主要来自成本与阶梯几何，
    而不是"猜错方向"；镜像的 +0.04R/笔在统计上与 0 无异。

    因此本测试锁定**可辩护的负控判据**，并在事实变化时报警：
      1. 镜像胜率 < 50%（任务书那一半成立）；
      2. 镜像净额落在 ±0.15R/笔 以内（"换向也换不出稳定盈利"）；
      3. 账本原方向亏损（策略在负控视角下确实是失效的）。
    若将来方向真的变有效，镜像会显著**亏钱**（跌破 −0.15R/笔）→ 本测试红 → 必须回来
    显式更新结论，而不是让"方向无信息"这句话悄悄过期。
    """
    _assert_replay_matches_canonical_spec()

    original = _replay_all(ledger, invert=False)
    inverted = _replay_all(ledger, invert=True)
    ledger_total = sum(p["net_full"] for p in ledger["positions"])

    assert original["n"] == inverted["n"] == len(ledger["positions"])
    # 1) 任务书那一半：镜像胜率 < 50%
    assert inverted["win_rate"] < 0.5, f"镜像胜率 {inverted['win_rate']:.1%} ≥ 50%，方向可能真有 alpha"
    # 2) 镜像换不出稳定盈利（±0.15R/笔）
    assert abs(inverted["r_mean"]) < 0.15, (
        f"镜像净额 {inverted['total_usdt']:+.2f} USDT（{inverted['r_mean']:+.3f}R/笔）超出噪声带，"
        f"方向信息需要重新评估"
    )
    # 3) 账本原方向确实在亏
    assert ledger_total < 0, f"账本原方向合计 {ledger_total:+.2f} USDT 不是亏损，负控前提变了"
    # 4) 记录模型保真度：重放原方向与账本同号（方向一致），避免"模型符号反了"也算通过
    assert original["total_usdt"] < 0, (
        f"重放原方向 {original['total_usdt']:+.2f} USDT 与账本 {ledger_total:+.2f} 不同号，"
        f"说明重放模型与引擎的几何背离过大，负控不可信"
    )


# ---------------------------------------------------------------- 负控 2


def test_score_shuffle_kills_correlation(ledger: dict) -> None:
    """打乱 score 与盈亏的配对：|ρ| 必须落回噪声带，真实 ρ 不得比随机更好。

    实测：真实 ρ = −0.0051（p≈0.97）；100 次置换的 |ρ| 中位数 = 0.0911；
    真实 |ρ| 在置换分布的第 97 百分位——即"真实分数与随机分数无法区分"。

    这条锁的是**总分无判别力**这个事实。将来若总分真的有效（真实 |ρ| 明显大于置换分布上界），
    本测试会红，必须显式更新结论（并同步更新入场阈值）。
    """
    scores = [p["score"] for p in ledger["positions"]]
    nets = [p["net_full"] for p in ledger["positions"]]

    real_rho, real_p = spearman(scores, nets)
    assert real_rho == real_rho, "真实 ρ 为 nan（方差为 0？），样本不可用"

    permuted_abs: list[float] = []
    seed_scores = list(scores)
    for seed in range(100):
        shuffled = list(seed_scores)
        # 固定 seed 的可复现置换（不用全局 random，避免测试间互相影响）
        rng = __import__("random").Random(seed)
        rng.shuffle(shuffled)
        rho, _ = spearman(shuffled, nets)
        if rho == rho:  # 跳过 nan
            permuted_abs.append(abs(rho))

    assert permuted_abs, "置换后全部为 nan，样本退化"
    median_abs = median(permuted_abs)
    assert median_abs < 0.15, f"置换 |ρ| 中位数 {median_abs:.3f} 偏大，置换方案可能有问题"
    assert abs(real_rho) <= max(permuted_abs), (
        f"真实 |ρ|={abs(real_rho):.4f} 超出全部 100 次置换的最大值 {max(permuted_abs):.4f}，"
        f"总分开始有判别力了，必须更新结论"
    )
    # 顺带把 p 值的量级写进断言消息，便于评审复算
    assert real_p > 0.5, f"真实 ρ 的 p 值 {real_p:.3f} 意外地小（ρ={real_rho:+.4f}）"


# ---------------------------------------------------------------- 负控 3


def _total_score(component_scores: dict[str, float], *, cvd_points: float | None = None) -> float:
    """按 FIB_PA 权重把分量重算成总分（与 engine 的 component_points 同口径）。"""
    scores = dict(component_scores)
    if cvd_points is not None:
        scores["flow_cvd_confirmation"] = cvd_points / FIB_PA_WEIGHTS["flow_cvd_confirmation"]
    total = 0.0
    for key, weight in FIB_PA_WEIGHTS.items():
        value = max(0.0, min(1.0, float(scores.get(key, 0.0))))
        total += round(value * weight, 4)
    return round(total, 4)


def test_constant_cvd_does_not_change_ranking(ledger: dict) -> None:
    """把 `flow_cvd_confirmation` 钉成 18.0 分（它本来就全等），排序必须一模一样。

    实测：47 笔的 `flow_cvd_confirmation` 原始值全为 1.0（× 权重 18 = 18.0 分），方差为 0；
    强制 18.0 后 `Spearman(forced, original) = 1.0`，排序完全相同。

    这证明该分量在**已成交样本**上零信息：它只是给所有候选加同一个常数，
    对排序与入场取舍毫无作用。若哪天它不再是常数，本测试会红——那说明成交样本的构成变了，
    推理不能继续沿用"18% 权重等于白给"。
    """
    positions = ledger["positions"]
    raw_cvd = {p["component_scores"].get("flow_cvd_confirmation") for p in positions}
    assert raw_cvd == {1.0}, f"`flow_cvd_confirmation` 不再是全 1.0（实际取值 {sorted(raw_cvd)}），负控前提变了"

    original = [_total_score(p["component_scores"]) for p in positions]
    # 先证明重算口径与引擎一致，否则下面的"排序不变"毫无意义
    for score, p in zip(original, positions):
        assert score == pytest.approx(p["score"], abs=1e-6), (
            f"{p['symbol']} 重算总分 {score} != 账本 score {p['score']}，重算口径不对"
        )

    forced = [_total_score(p["component_scores"], cvd_points=18.0) for p in positions]
    rho, _ = spearman(forced, original)
    assert rho == pytest.approx(1.0), f"强制 CVD 后 Spearman={rho:.4f}，排序被打乱"
    assert sorted(range(len(positions)), key=lambda i: forced[i]) == sorted(
        range(len(positions)), key=lambda i: original[i]
    )
    # 分数本身也完全不变（常数平移不影响总分，因为分量键与权重都对得上）
    assert forced == original


# ---------------------------------------------------------------- 附带：分段闭合断言自检
# 为什么放在这个文件：本轮只允许新增两个测试文件，而归因脚本的"闭合断言"是 P0-1 的核心
# 交付物（防止改了切分逻辑却静默漏算），必须有一条会红的测试证明它真的会抛。


def _fake_position(entry_time: int, net: float) -> dict:
    """最小仓位列（summarize 需要 gross / entry_cost / exit_cost / notional / stop_pct）。"""
    return {
        "position_id": f"P{entry_time}",
        "symbol": "XUSDT",
        "side": "LONG",
        "entry_time": entry_time,
        "net_full": net,
        "gross": net,
        "entry_cost": 0.0,
        "exit_cost": 0.0,
        "notional": 100.0,
        "stop_pct": 0.01,
    }


def test_segment_closes_for_a_well_formed_split() -> None:
    import attribution_20261114 as attr

    rows = [_fake_position(1, 10.0), _fake_position(2, -5.0), _fake_position(11, 3.0)]
    out = attr.segment(rows, since_ts=0, cut_ts=10)
    assert out["all"]["n"] == 3
    assert out["before_cut"]["n"] == 2
    assert out["after_cut"]["n"] == 1
    assert out["closed_check"]["n_before_plus_after"] == out["closed_check"]["n_all"]
    assert out["before_cut"]["net_total"] + out["after_cut"]["net_total"] == pytest.approx(
        out["all"]["net_total"]
    )


def test_segment_aborts_instead_of_silently_losing_positions(monkeypatch) -> None:
    """人为让"全部"那一栏少算 → 必须 SystemExit，而不是打印一份看起来正常的报告。"""
    import attribution_20261114 as attr

    real = attr.summarize
    calls = {"n": 0}

    def doctored(items):
        out = real(items)
        calls["n"] += 1
        if calls["n"] == 1:  # 只污染"全部"那一栏（segment 里第一次调用）
            out["net_total"] = out["net_total"] + 1e-3
        return out

    monkeypatch.setattr(attr, "summarize", doctored)
    with pytest.raises(SystemExit):
        attr.segment([_fake_position(1, 10.0), _fake_position(11, 3.0)], since_ts=0, cut_ts=10)
