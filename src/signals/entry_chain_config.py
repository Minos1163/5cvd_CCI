from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping


# 2026-11-09：以下字段声明保留但**无任何读取点**（静态审计 + 人工 grep 双重确认，
# 见 scripts/audit_config_wiring.py 与 docs/audit/config-wiring-20261109.json）。
#
# 为什么保留声明而不是删除：`from_mapping` 对未知键会 raise，删除字段会让仍带这些
# 键的历史配置（含 VPS 生产配置）启动失败。保留声明 + 从配置文件中清理，是唯一
# 既能清理又不破坏兼容的路径。
#
# 为什么不接线：这些参数分别影响 fib 摆动点识别、EMA200 闸门与 scout 门槛；接线
# 等于改变信号、改变交易，属于“改策略参数”，不在本次治理范围。
DEAD_CONFIG_KEYS: frozenset[str] = frozenset({
    "base_direct_exposure_pct",
    "probe_fraction",
    "ema200_buffer_pct",
    "ema200_min_bars_stable",
    "fib_extension_exhaustion_mult",
    "fib_level_tolerance_atr_mult",
    "fib_swing_fractal_k",
    "fib_swing_lookback_15m",
    "fib_swing_lookback_1h",
    "fib_swing_min_atr_mult",
    "fib_swing_min_spacing_bars",
    "scout_micro_non_rr_min_score",
    "scout_micro_targeted_long_min_score",
    "scout_micro_targeted_long_min_pa_score",
    "scout_micro_targeted_long_min_rr_score",
})


# `scoring_architecture` 的合法取值（见 EntryChainConfig 字段注释）。
# "auto" = 按两个历史布尔开关推断；其余为显式架构。空串按 "auto" 处理（历史配置友好）。
_AUTO_ARCHITECTURE = "auto"
_SCORING_ARCHITECTURES = frozenset({_AUTO_ARCHITECTURE, "fib_pa", "ema", "base"})

# `scoring_repair_v2` 的合法取值（见 EntryChainConfig 字段注释）。空串按 "off" 处理。
_SCORING_REPAIR_MODES = frozenset({"off", "shadow", "on"})

# `log_profile` 的合法取值：full = 现有全部输出；lean = 停写无读取方的文件并精简
# runtime 日志（见 src/observability/decision_audit.py 与 docs/plans/2026-11-21-log-slimming.md）。
_LOG_PROFILES = frozenset({"full", "lean"})


@dataclass(frozen=True)
class ExplicitWatchlistEntry:
    """显式白名单条目(评审 7.2 规格):新增符号一律先 scout_only,达标后 promotion。"""

    symbol: str
    added_date: str = ""
    rationale: str = ""
    scan_scope: str = "scout_only"  # scout_only | full_pipeline
    review_period_days: int = 14
    promotion_criteria: Mapping[str, Any] = field(default_factory=lambda: {"min_samples": 15, "pf_min": 1.0})

    @property
    def normalized_symbol(self) -> str:
        return self.symbol.strip().upper()


@dataclass(frozen=True)
class EntryChainConfig:
    direct_threshold: float = 82.0
    probe_threshold: float = 70.0
    watch_threshold: float = 60.0
    min_direction_direct_score: float = 0.64
    min_quality_direct_score: float = 0.73
    min_trigger_direct_score: float = 0.92
    min_cvd_direct_score: float = 0.61
    min_direction_probe_score: float = 0.56
    min_quality_probe_score: float = 0.45
    min_trigger_probe_score: float = 0.67
    min_cvd_probe_score: float = 0.45
    high_vol_atr_pct: float = 0.035
    low_vol_atr_pct: float = 0.010
    macro_daily_drop_block_pct: float = -0.05
    macro_weekly_drop_block_pct: float = -0.15
    direct_liquidity_ratio: float = 20.0
    probe_liquidity_ratio: float = 8.0
    max_active_symbols: int = 5
    daily_max_trades_base: int = 4
    min_daily_trades: int = 1
    max_symbol_trades_per_day: int = 1
    max_same_direction_exposure_pct: float = 1.20
    max_total_exposure_pct: float = 1.50
    margin_buffer_pct: float = 0.20
    base_direct_exposure_pct: float = 0.20  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    max_large_cap_exposure_pct: float = 0.30
    max_mainstream_exposure_pct: float = 0.20
    max_high_beta_exposure_pct: float = 0.10
    probe_fraction: float = 0.25  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    direct_risk_pct: float = 0.008
    probe_risk_pct: float = 0.003
    min_stop_pct: float = 0.005
    max_stop_pct: float = 0.04
    # 评分架构唯一枚举（2026-11-14 评审 §3.3）：`"auto" | "fib_pa" | "ema" | "base"`。
    #
    # 为什么需要它：历史上有两个布尔开关（`use_fib_pa_architecture` / `use_ema_architecture`），
    # 两者同时为 true 时由 `dynamic_weights` 的短路顺序**隐式**决定用哪组权重——
    # 配置里写着两个 true，却没人能从配置直接回答"这套到底按哪组权重打分"。
    # 生产配置 `entry_chain.dry_run_regime_shadow.json` 正是这种状态。
    #
    # 语义：
    # - `"auto"`（默认）：完全按两个布尔开关推断，**与引入本字段之前逐位一致**；
    # - 显式值：以本字段为准，忽略两个布尔开关（两个开关仍参与冲突告警）。
    #
    # 默认 `"auto"` 保证所有历史配置（含 VPS 上在跑的那份）行为不变。
    scoring_architecture: str = "auto"
    use_ema_architecture: bool = False
    ema200_gate_mode: str = "hard"
    ema200_buffer_pct: float = 0.003  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    ema200_min_bars_stable: int = 3  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    ema50_min_for_direct: float = 0.60
    ema50_min_for_probe: float = 0.40
    disable_probe: bool = False
    probe_conditions: Mapping[str, Any] | None = None
    blacklist_symbols: tuple[str, ...] = ()
    watch_only_symbols: tuple[str, ...] = ()
    observation_only_symbols: tuple[str, ...] = ()
    scout_micro_symbols: tuple[str, ...] = ()
    scout_micro_rr_gap_block_symbols: tuple[str, ...] = ()
    scout_micro_targeted_long_symbols: tuple[str, ...] = ()
    scout_micro_scout_only_symbols: tuple[str, ...] = ()
    scout_micro_min_score: float = 82.0
    scout_micro_non_rr_min_score: float = 85.0  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    scout_micro_targeted_long_min_score: float = 82.0  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    scout_micro_targeted_long_min_pa_score: float = 18.0  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    scout_micro_targeted_long_min_rr_score: float = 3.0  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    scout_micro_scout_only_min_score: float = 85.0
    scout_micro_scout_only_min_fib_score: float = 12.0
    scout_micro_scout_only_min_pa_score: float = 10.0
    scout_micro_scout_only_min_rr_score: float = 4.0
    scout_micro_high_score_long_offset_min_score: float = 85.0
    scout_micro_high_score_long_offset_min_pa_score: float = 18.0
    scout_micro_high_score_long_offset_min_fib_score: float = 15.0
    scout_micro_high_score_long_offset_min_cvd_score: float = 14.0
    scout_micro_high_score_long_offset_min_rr_score: float = 2.0
    scout_micro_high_score_long_offset_quadrants: tuple[str, ...] = ("Q1", "Q3")
    scout_micro_fib_continuation_min_score: float = 82.0
    scout_micro_fib_continuation_min_ema_score: float = 16.0
    scout_micro_fib_continuation_min_cvd_score: float = 14.0
    scout_micro_fib_continuation_min_pa_score: float = 18.0
    scout_micro_watch_only_promotion_min_score: float = 85.0
    quadrant_trend_ema_min: float = 15.0
    quadrant_price_action_min: float = 10.0
    quadrant_flow_cvd_min: float = 14.0
    quadrant_cci_min: float = 7.0
    scout_micro_q1_rr_gap_enabled: bool = False
    scout_micro_q1_rr_gap_min_score: float = 82.0
    scout_micro_q1_rr_gap_min_cvd_score: float = 0.0
    scout_micro_q3_to_q1_enabled: bool = False
    scout_micro_q3_to_q1_min_score: float = 85.0
    scout_micro_q3_to_q1_min_cvd_score: float = 16.0
    scout_micro_q3_to_q1_confirm_bars: int = 3
    scout_micro_q3_to_q1_confirm_pa_score: float = 15.0
    scout_micro_q2_pending_enabled: bool = False
    scout_micro_q2_pending_min_score: float = 70.0
    scout_micro_q2_pending_min_pa_score: float = 18.0
    scout_micro_q2_pending_confirm_bars: int = 6
    scout_micro_q2_pending_confirm_cci_score: float = 9.0
    quadrant_pending_state_enabled: bool = True
    dry_run_q1_trend_launch_enabled: bool = False
    dry_run_q1_trend_launch_min_score: float = 82.0
    dry_run_q1_trend_launch_min_pa_score: float = 18.0
    dry_run_q1_trend_launch_min_fib_score: float = 15.0
    dry_run_q1_trend_launch_min_cvd_score: float = 16.0
    dry_run_q1_trend_launch_min_rr_score: float = 0.5
    dry_run_q1_trend_launch_extreme_ratio_min: float = 0.20
    dry_run_q1_trend_launch_extreme_ratio_max: float = 0.80
    dry_run_q1_trend_launch_base_exposure_pct: float = 0.025
    dry_run_q1_trend_launch_exit_mode: str = "trend_capture"
    dry_run_q1_trend_launch_allow_degraded_data: bool = False
    # q1 通道降级为"只记录不覆盖"（2026-11-14 评审 §14 P0 A5）。默认 False = 现状：
    # q1 通道返回非 None 就**替换**主决策（`annotate_replacement` 写 replaced_decision_id）。
    # 置 True 时：主决策保持不动，q1 的决策只写进 payload 的 `shadow_decision`，
    # `decision_origin` 仍为 primary，**不写** replaced_decision_id。
    # 目的：先并行收集"q1 覆盖 vs 不覆盖"的样本差，再决定是否关闭通道；
    # 默认关闭所以生产行为逐位不变。
    q1_trend_launch_shadow_only: bool = False
    mirror_ab_enabled: bool = False
    mirror_ab_mode: str = "active"  # active | shadow_only(08-18 评审:mirror 降级 shadow,记录不计敞口/熔断)
    mirror_ab_payoff_pilot_enabled: bool = False
    mirror_ab_payoff_early_breakeven_trigger_r: float = 1.0
    mirror_ab_payoff_trend_trigger_r: float = 1.2
    mirror_ab_min_score: float = 85.0
    mirror_ab_notional: float = 50.0
    mirror_ab_allowed_reasons: tuple[str, ...] = ()
    mirror_ab_include_q1_watch: bool = False
    paper_ab_auto_report_enabled: bool = False
    paper_ab_report_closed_trade_interval: int = 20
    paper_ab_auto_switch_enabled: bool = False
    paper_ab_auto_switch_min_reports: int = 2
    paper_ab_auto_switch_min_closed_trades: int = 40
    paper_ab_auto_switch_payoff_mult: float = 1.3
    # 2026-10-31:第三条 AB 臂。只保留静态止损 + TP 阶梯 + 32 根上限,
    # 关掉 Q3_DEFENSIVE_REDUCE / Q4_DEFENSIVE_EXIT(防御性覆盖层)。
    # 动机:6 天 51 笔里,防御层触发过的 35 笔相对"纯阶梯"回放平均差 -0.2R,
    # 未触发的 16 笔差 +0.009R(引擎可复现账本)。需要并行收集样本,不改现有两臂。
    paper_ab_pure_ladder_enabled: bool = False
    dry_run_q1_green_channel_enabled: bool = False
    dry_run_q1_green_channel_notional_mult: float = 0.5
    dry_run_q1_green_channel_min_score: float = 85.0
    dry_run_q1_green_channel_min_pa_score: float = 18.0
    dry_run_q1_green_channel_min_cvd_score: float = 16.0
    dry_run_q1_green_channel_base_exposure_pct: float = 0.05
    dry_run_q1_green_channel_exit_mode: str = "trend_capture"
    experiment_war_fund_loss_limit: float = -150.0
    experiment_daily_loss_limit: float = -200.0
    scout_micro_same_side_cooldown_hours: int = 2
    scout_micro_initial_stop_cooldown_hours: int = 6
    scout_micro_mission_stop_circuit_enabled: bool = False
    scout_micro_mission_stop_circuit_count: int = 3
    scout_micro_mission_stop_circuit_hours: int = 12
    scout_micro_allow_degraded_data: bool = False
    scout_micro_reversal_pivot_enabled: bool = False
    scout_micro_reversal_pivot_min_score: float = 70.0
    scout_micro_reversal_pivot_max_cvd_score: float = 16.0
    scout_micro_reversal_pivot_max_cci_score: float = 10.0
    scout_micro_reversal_pivot_notional: float = 25.0
    scout_micro_notional: float = 50.0
    scout_micro_leverage: int = 1
    paper_exit_mode: str = "legacy"
    paper_exit_trend_trigger_r: float = 1.5
    paper_exit_trailing_r_mult: float = 1.0
    scout_micro_exit_mode: str = "legacy"
    scout_micro_exit_trend_trigger_r: float = 1.5
    scout_micro_exit_trailing_r_mult: float = 1.0
    # 评分修复 v2 三态（2026-11-21 评审 P1-1）：`"off" | "shadow" | "on"`。
    #
    # 背景：2026-11-14 的 47 笔样本里 `main_probe` 19 笔亏 129 USDT（胜率 10.5%），
    # 其中 12 笔被 `COST_BREAKEVEN_TIMEOUT` 平掉；分项归因显示 RR 分量实际上只是
    # **止损宽度的代理**（Spearman(stop_pct, rr)=+0.859），CVD 分量在成交样本上方差为 0。
    # 修复方向是换权重（RR 8→12、CVD 18→14、PA 22→20）+ 换算法（RR 两段式、CVD 连续化），
    # 但"改分就改交易"，所以默认必须关闭：
    # - "off"（默认）：逐位等于当前行为，v2 一律不计算；
    # - "shadow"：额外算一份 v2 分数写进 payload（`repair_v2_score` /
    #   `repair_v2_components` / `cvd_signed_ratio`），**action / score 仍用旧值**；
    # - "on"：v2 分量 + v2 权重生效（`score` 用 v2）。
    scoring_repair_v2: str = "off"
    # CVD 连续化是否随 v2 一起启用（2026-11-21 team-lead 裁定：必须能单独关）。
    #
    # 为什么拆开：2026-11-21 实测 47 笔里，CVD 从 v1 的二值（恒 1.0×18=18 分）换成 v2 的
    # 成交量加权方向比后，单项就压掉 **−11.7 分**（`signed_ratio` 均值 −0.09，偏卖方），
    # 直接把 DIRECT 从 16 笔压到 1 笔——那是"全面收紧闸门"，不是"评分优化"。
    # 而且 `signed_ratio` 测的是**短期反转**，与"趋势确认"的语义相反，方向本身就存疑。
    # 与 RR 两段式混在一起评估，会让 CVD 的副作用掩盖 RR 的真实效果。
    #
    # 组合语义（与 `scoring_repair_v2` 正交）：
    #   repair_v2_cvd_enabled=False + shadow → 只切 RR v2 + 新权重，CVD 仍走旧二值
    #   repair_v2_cvd_enabled=True  + shadow → RR v2 + 新权重 + CVD v2
    #   repair_v2_cvd_enabled=False + on     → RR v2 + 新权重生效，CVD 保持旧值
    #   任何取值 + off                        → 完全不动
    repair_v2_cvd_enabled: bool = False
    # probe 成本超时自适应（2026-11-21 评审 P1-4）：默认关闭 = 固定 `max_hold_bars//4`（8 根）。
    # 打开后仅对 `action == "PROBE"` 生效：成本占 R 越大，超时窗口越长（8→16 根），
    # 因为 20bps 往返成本在 probe 的小仓位上占到 0.19R，固定 8 根会让它们被系统性
    # 扫成小额亏损（11-14 的 19 笔 probe 里 12 笔死于该规则）。见
    # `paper_trading.adaptive_cost_timeout_bars`。
    #
    # **2026-11-21 实测：这个假设被数据否定，开关保留但不要启用。**
    # 实际死于 `COST_BREAKEVEN_TIMEOUT` 的 14 笔 `cost_R` 全在 0.112–0.181（< 0.19 标定点），
    # 公式对它们一根都不放宽（19 笔 probe 全部仍是 8 根）；根因是"8 根内价格几乎没动"，
    # 不是"成本占比高"。拿到那 14 笔的价格位移分布之前，不要调 `typical_cost_r`
    # 或取整方式。详见 `paper_trading.adaptive_cost_timeout_bars` 的 docstring。
    probe_cost_timeout_adaptive: bool = False
    dry_run_symbols: tuple[str, ...] = ()
    explicit_watchlist: tuple[ExplicitWatchlistEntry, ...] = ()
    dry_run_symbol_source: str = "configured"
    dry_run_rank_start: int = 3
    dry_run_rank_end: int = 25
    # 目标标的数：0 = 不限制（rank 区间内能取几个取几个，历史行为）。
    # >0 时按市值排名从 rank_start 往下取，凑满该数量即停，rank_end 退化为上限保护。
    # 为什么要有它：rank 区间是"范围"、不是"数量"，同一区间在不同日期取到的标的数
    # 会随排名波动（实测 2026-11-14：rank 3-25 只命中 14 个可交易非稳定币）。
    # 想要"固定 25 个标的"必须按数量收敛，否则标的池每天都在变。
    dry_run_universe_size: int = 0
    dry_run_warmup_15m_bars: int = 240
    use_fib_pa_architecture: bool = False
    fib_swing_fractal_k: int = 2  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    fib_swing_min_atr_mult: float = 1.2  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    fib_swing_min_spacing_bars: int = 6  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    fib_swing_lookback_15m: int = 50  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    fib_swing_lookback_1h: int = 30  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    fib_extension_exhaustion_mult: float = 1.618  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    fib_level_tolerance_atr_mult: float = 0.5  # DEAD: 无读取点，见 DEAD_CONFIG_KEYS
    pa_min_direct_score: float = 6.0
    fib_min_direct_score: float = 6.0
    rr_min_direct_score: float = 2.0
    leverage_5x_fib_min: float = 13.0
    leverage_5x_pa_min: float = 9.0
    leverage_5x_cci_min: float = 7.0
    leverage_5x_rr_min: float = 4.0
    weak_edge_direct_min_score: float = 82.0
    weak_edge_direct_max_score: float = 85.0
    weak_edge_probe_min_score: float = 77.0
    weak_edge_probe_max_score: float = 85.0
    rolling_symbol_cooldown_enabled: bool = False
    rolling_symbol_cooldown_stop_threshold: int = 2
    rolling_symbol_cooldown_window_hours: int = 48
    rolling_symbol_cooldown_hours: int = 24
    long_threshold_offset: float = 0.0
    short_threshold_offset: float = 0.0
    long_min_direction_direct_score: float | None = None
    long_min_quality_direct_score: float | None = None
    long_min_trigger_direct_score: float | None = None
    long_min_cvd_direct_score: float | None = None
    short_min_direction_direct_score: float | None = None
    short_min_quality_direct_score: float | None = None
    short_min_trigger_direct_score: float | None = None
    short_min_cvd_direct_score: float | None = None
    enable_long_context_discounts: bool = False
    long_overextension_quality_mult: float = 0.70
    long_upper_wick_trigger_mult: float = 0.60
    long_chase_trigger_mult: float = 0.75
    long_cvd_weak_mult: float = 0.80
    long_cvd_weak_threshold: float = 0.80
    long_overextension_watch_enabled: bool = False
    long_chase_watch_enabled: bool = False
    post_initial_stop_cooldown_enabled: bool = False
    post_initial_stop_cooldown_hours: int = 4
    portfolio_stop_circuit_enabled: bool = False
    portfolio_stop_circuit_count: int = 3
    portfolio_stop_circuit_hours: int = 4
    portfolio_daily_loss_circuit_enabled: bool = False
    portfolio_daily_loss_limit: float = -30.0
    max_single_trade_risk_pct: float = 0.0075
    # 风险优先仓位(2026-10-19 网络交流后新增,默认关闭):
    # 关闭时沿用旧口径——名义先按 equity×risk_pct/stop_pct 算,再用
    # equity×max_single_trade_risk_pct/(stop_pct×leverage) 封顶,于是杠杆越低名义越小、
    # 单笔风险与杠杆成反比。打开后改为「风险定额」:单笔风险 = min(risk_pct, 上限),
    # 名义 = 风险额/stop_pct;杠杆只决定保证金占用,不再改变单笔风险。
    # 打开会让同一 risk_pct 下的名义显著变大(旧口径被杠杆上限压掉约 3 倍),
    # 必须先用独立配置 + dry-run/paper 验证,不要直接改线上配置。
    risk_first_sizing_enabled: bool = False
    # 五正交因子 P0 影子(2026-09-27 裁定报告):只写 component_points_v2 记录字段,
    # 不参与 total_score/门槛/杠杆/action;置 false 即可完全回滚影子记录。
    five_factor_shadow_enabled: bool = True
    # 声明式入场闸门(2026-10-19 条件扫描):空 = 关闭。规则形如
    # [{"feature": "trend_ema_context", "op": ">=", "value": 0.72}]，
    # 参数必须来自 reports/analysis/edge-scan-*/selected.json，不允许手调。
    entry_gates: tuple[Mapping[str, Any], ...] = ()
    # 评分核开关(2026-10-20):"legacy" = 现有 15m 加权评分(默认,行为不变);
    # "s1_shadow" = 额外计算 4h SMA50/SMA200 趋势状态,只写入 decisions.jsonl 的
    # `s1_core` 字段,**不参与 total_score / action / 杠杆 / 名义**。
    # 见 src/signals/score_core.py 与 docs/analysis/s1_overlay_oos_2026-10-20.md。
    score_core: str = "legacy"
    # 组合层仓位规则(2026-10-20):"off" | "shadow" | "cap"。
    # 4h SMA50/SMA200 决定"允许的最大仓位"(1/0);"cap" 时目标 0 会拦截新开仓。
    # 参数由预登记 walk-forward 选出(scripts/analysis/regime_overlay_wf_20261020.py),
    # 见 docs/analysis/overlay_on_majors_2026-10-20.md。默认 off,行为不变。
    regime_overlay: str = "off"
    # 日志档位(2026-11-21 日志瘦身):"full"(默认,与改动前逐位一致) | "lean"。
    # lean 下停写无读取方的 attribution/order_drafts/scout_decisions/gate_rejections.csv,
    # 并对 decisions.jsonl 做字段瘦身、跳过每标的每根的明细 runtime 行。
    # 代码默认 full，保证所有历史配置（含 VPS 生产配置）行为不变。
    log_profile: str = "full"

    def __post_init__(self) -> None:
        if self.log_profile not in _LOG_PROFILES:
            raise ValueError(
                f"invalid log_profile '{self.log_profile}' (allowed: {sorted(_LOG_PROFILES)})"
            )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "EntryChainConfig":
        allowed = {item.name for item in fields(cls)}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError(f"unknown entry-chain config keys: {unknown}")
        values = {key: data[key] for key in data if key in allowed}
        if "blacklist_symbols" in values:
            values["blacklist_symbols"] = _normalize_symbols(values["blacklist_symbols"])
        if "watch_only_symbols" in values:
            values["watch_only_symbols"] = _normalize_symbols(values["watch_only_symbols"])
        if "observation_only_symbols" in values:
            values["observation_only_symbols"] = _normalize_symbols(values["observation_only_symbols"])
        if "scout_micro_symbols" in values:
            values["scout_micro_symbols"] = _normalize_symbols(values["scout_micro_symbols"])
        if "scout_micro_rr_gap_block_symbols" in values:
            values["scout_micro_rr_gap_block_symbols"] = _normalize_symbols(values["scout_micro_rr_gap_block_symbols"])
        if "scout_micro_targeted_long_symbols" in values:
            values["scout_micro_targeted_long_symbols"] = _normalize_symbols(values["scout_micro_targeted_long_symbols"])
        if "scout_micro_scout_only_symbols" in values:
            values["scout_micro_scout_only_symbols"] = _normalize_symbols(values["scout_micro_scout_only_symbols"])
        if "mirror_ab_allowed_reasons" in values:
            values["mirror_ab_allowed_reasons"] = _normalize_strings(values["mirror_ab_allowed_reasons"])
        if "mirror_ab_mode" in values:
            mode = str(values["mirror_ab_mode"]).strip().lower()
            if mode not in {"active", "shadow_only"}:
                raise ValueError(f"invalid mirror_ab_mode '{mode}' (allowed: active, shadow_only)")
            values["mirror_ab_mode"] = mode
        if "scoring_repair_v2" in values:
            repair = str(values["scoring_repair_v2"] or "off").strip().lower()
            if repair not in _SCORING_REPAIR_MODES:
                raise ValueError(
                    f"invalid scoring_repair_v2 '{repair}' (allowed: {sorted(_SCORING_REPAIR_MODES)})"
                )
            values["scoring_repair_v2"] = repair
        if "scoring_architecture" in values:
            architecture = str(values["scoring_architecture"] or _AUTO_ARCHITECTURE).strip().lower()
            if architecture not in _SCORING_ARCHITECTURES:
                raise ValueError(
                    f"invalid scoring_architecture '{architecture}' "
                    f"(allowed: {sorted(_SCORING_ARCHITECTURES)})"
                )
            values["scoring_architecture"] = architecture
        if "dry_run_symbols" in values:
            values["dry_run_symbols"] = _normalize_symbols(values["dry_run_symbols"])
        if "explicit_watchlist" in values:
            values["explicit_watchlist"] = _parse_explicit_watchlist(values["explicit_watchlist"], data.get("blacklist_symbols", ()))
        if "entry_gates" in values:
            gates = values["entry_gates"] or ()
            if not isinstance(gates, (list, tuple)):
                raise ValueError("entry_gates must be a list of rule objects")
            for item in gates:
                if not isinstance(item, dict):
                    raise ValueError("each entry_gates item must be an object")
            values["entry_gates"] = tuple(gates)
        if "log_profile" in values:
            profile = str(values["log_profile"] or "full").strip().lower()
            if profile not in _LOG_PROFILES:
                raise ValueError(
                    f"invalid log_profile '{profile}' (allowed: {sorted(_LOG_PROFILES)})"
                )
            values["log_profile"] = profile
        return cls(**values)


def load_entry_chain_config(path: str | Path) -> EntryChainConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("entry-chain config must be a JSON object")
    return EntryChainConfig.from_mapping(payload)


def _normalize_symbols(values: Any) -> tuple[str, ...]:
    return tuple(symbol for item in values if (symbol := str(item).strip().upper()))


def _normalize_strings(values: Any) -> tuple[str, ...]:
    return tuple(value for item in values if (value := str(item).strip().upper()))


_ALLOWED_SCOPES = ("scout_only", "full_pipeline")


def _parse_explicit_watchlist(values: Any, blacklist: Any) -> tuple[ExplicitWatchlistEntry, ...]:
    """解析 explicit_watchlist 配置,校验:重复符号、非法 scan_scope、与黑名单冲突。"""
    if not isinstance(values, list):
        raise ValueError("explicit_watchlist must be a list")
    blacklist_set = {str(s).strip().upper() for s in (blacklist or ())}
    seen: set[str] = set()
    entries: list[ExplicitWatchlistEntry] = []
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("each explicit_watchlist entry must be an object")
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("explicit_watchlist entry missing symbol")
        if symbol in seen:
            raise ValueError(f"duplicate explicit_watchlist symbol: {symbol}")
        if symbol in blacklist_set:
            raise ValueError(f"explicit_watchlist symbol conflicts with blacklist: {symbol}")
        raw_scope = item.get("scan_scope")
        if raw_scope is None:
            scope = "scout_only"  # 缺失 → 首次添加默认 scout_only(评审规格)
        else:
            scope = str(raw_scope).strip().lower()
            if scope not in _ALLOWED_SCOPES:
                raise ValueError(f"invalid scan_scope '{scope}' for {symbol} (allowed: {_ALLOWED_SCOPES})")
        promotion = item.get("promotion_criteria")
        if promotion is not None and not isinstance(promotion, dict):
            raise ValueError(f"promotion_criteria for {symbol} must be an object")
        seen.add(symbol)
        entries.append(
            ExplicitWatchlistEntry(
                symbol=symbol,
                added_date=str(item.get("added_date") or ""),
                rationale=str(item.get("rationale") or ""),
                scan_scope=scope,
                review_period_days=int(item.get("review_period_days") or 14),
                promotion_criteria=dict(promotion) if promotion else {"min_samples": 15, "pf_min": 1.0},
            )
        )
    return tuple(entries)
