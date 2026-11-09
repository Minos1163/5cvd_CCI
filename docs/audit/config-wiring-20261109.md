# EntryChainConfig 配置接线审计

- 生成日期: 2026-11-09
- commit: `5e2a2e0989534adc083470329cbfc096e50eb5b8`(工作区有未提交改动: True)
- 数据类: `EntryChainConfig`
- 扫描文件数: 203
- 字段总数: 201 | LIVE_READ: 181 | DYNAMIC_READ: 4 | DECLARED_ONLY: 16 | UNKNOWN_KEY: 0

> **三类状态**:`LIVE_READ` 有直接读取;`DYNAMIC_READ` 只有 `getattr`/`vars` 命中,
> 静态可见但运行时是否命中取决于数据;`DECLARED_ONLY` 两遍都不可见。
> **`DECLARED_ONLY` 是「待人工确认」的候选,不是死代码结论** —— 持有者变量名不以
> `cfg`/`config` 结尾、或经 `**cfg` 展开读取时仍会漏检。

## DYNAMIC_READ(仅动态路径,共 4 个)

| # | 字段 | 命中方式 | 位置 |
| --- | --- | --- | --- |
| 1 | `entry_gates` | getattr | `scripts/run_live_dry_run.py:1218` |
| 2 | `five_factor_shadow_enabled` | getattr | `scripts/run_live_dry_run.py:2832` |
| 3 | `risk_first_sizing_enabled` | getattr | `src/signals/entry_chain.py:724` |
| 4 | `score_core` | getattr | `scripts/run_live_dry_run.py:2687` |

## DECLARED_ONLY(静态与动态两遍都不可见,共 16 个)

| # | 字段 | 读取点数 |
| --- | --- | --- |
| 1 | `base_direct_exposure_pct` | 0 |
| 2 | `ema200_buffer_pct` | 0 |
| 3 | `ema200_min_bars_stable` | 0 |
| 4 | `explicit_watchlist` | 0 |
| 5 | `fib_extension_exhaustion_mult` | 0 |
| 6 | `fib_level_tolerance_atr_mult` | 0 |
| 7 | `fib_swing_fractal_k` | 0 |
| 8 | `fib_swing_lookback_15m` | 0 |
| 9 | `fib_swing_lookback_1h` | 0 |
| 10 | `fib_swing_min_atr_mult` | 0 |
| 11 | `fib_swing_min_spacing_bars` | 0 |
| 12 | `probe_fraction` | 0 |
| 13 | `scout_micro_non_rr_min_score` | 0 |
| 14 | `scout_micro_targeted_long_min_pa_score` | 0 |
| 15 | `scout_micro_targeted_long_min_rr_score` | 0 |
| 16 | `scout_micro_targeted_long_min_score` | 0 |

## LIVE_READ(共 181 个)

| # | 字段 | 读取点数 | 前几处位置 |
| --- | --- | --- | --- |
| 1 | `blacklist_symbols` | 6 | `scripts/audit_entry_gate_controls.py:134`<br>`scripts/audit_entry_gate_controls.py:135`<br>`scripts/audit_entry_gate_controls.py:235`<br>`scripts/audit_q1_trend_launch_hits.py:84`<br>`scripts/run_live_dry_run.py:1141` |
| 2 | `daily_max_trades_base` | 4 | `scripts/run_live_dry_run.py:551`<br>`scripts/vps_dry_run_healthcheck.py:37`<br>`src/signals/entry_chain.py:269`<br>`src/signals/entry_chain_gates.py:76` |
| 3 | `direct_liquidity_ratio` | 1 | `src/signals/entry_chain.py:156` |
| 4 | `direct_risk_pct` | 2 | `scripts/run_live_dry_run.py:545`<br>`src/signals/entry_chain.py:723` |
| 5 | `direct_threshold` | 6 | `scripts/audit_entry_gate_controls.py:262`<br>`scripts/replay_atom_chain.py:88`<br>`scripts/replay_symbol_chain.py:98`<br>`scripts/vps_dry_run_healthcheck.py:35`<br>`src/signals/entry_chain.py:175` |
| 6 | `disable_probe` | 1 | `src/signals/entry_chain.py:352` |
| 7 | `dry_run_q1_green_channel_base_exposure_pct` | 1 | `scripts/run_live_dry_run.py:608` |
| 8 | `dry_run_q1_green_channel_enabled` | 1 | `scripts/run_live_dry_run.py:603` |
| 9 | `dry_run_q1_green_channel_exit_mode` | 1 | `scripts/run_live_dry_run.py:609` |
| 10 | `dry_run_q1_green_channel_min_cvd_score` | 1 | `scripts/run_live_dry_run.py:607` |
| 11 | `dry_run_q1_green_channel_min_pa_score` | 1 | `scripts/run_live_dry_run.py:606` |
| 12 | `dry_run_q1_green_channel_min_score` | 1 | `scripts/run_live_dry_run.py:605` |
| 13 | `dry_run_q1_green_channel_notional_mult` | 1 | `scripts/run_live_dry_run.py:604` |
| 14 | `dry_run_q1_trend_launch_allow_degraded_data` | 2 | `scripts/run_live_dry_run.py:591`<br>`scripts/run_live_dry_run.py:1159` |
| 15 | `dry_run_q1_trend_launch_base_exposure_pct` | 2 | `scripts/run_live_dry_run.py:589`<br>`scripts/run_live_dry_run.py:1024` |
| 16 | `dry_run_q1_trend_launch_enabled` | 2 | `scripts/run_live_dry_run.py:583`<br>`scripts/run_live_dry_run.py:1155` |
| 17 | `dry_run_q1_trend_launch_exit_mode` | 2 | `scripts/run_live_dry_run.py:590`<br>`scripts/run_live_dry_run.py:1054` |
| 18 | `dry_run_q1_trend_launch_extreme_ratio_max` | 2 | `scripts/audit_q1_trend_launch_hits.py:85`<br>`scripts/run_live_dry_run.py:1184` |
| 19 | `dry_run_q1_trend_launch_extreme_ratio_min` | 2 | `scripts/audit_q1_trend_launch_hits.py:85`<br>`scripts/run_live_dry_run.py:1182` |
| 20 | `dry_run_q1_trend_launch_min_cvd_score` | 3 | `scripts/audit_q1_trend_launch_hits.py:89`<br>`scripts/run_live_dry_run.py:587`<br>`scripts/run_live_dry_run.py:1198` |
| 21 | `dry_run_q1_trend_launch_min_fib_score` | 3 | `scripts/audit_q1_trend_launch_hits.py:88`<br>`scripts/run_live_dry_run.py:586`<br>`scripts/run_live_dry_run.py:1197` |
| 22 | `dry_run_q1_trend_launch_min_pa_score` | 3 | `scripts/audit_q1_trend_launch_hits.py:87`<br>`scripts/run_live_dry_run.py:585`<br>`scripts/run_live_dry_run.py:1196` |
| 23 | `dry_run_q1_trend_launch_min_rr_score` | 3 | `scripts/audit_q1_trend_launch_hits.py:90`<br>`scripts/run_live_dry_run.py:588`<br>`scripts/run_live_dry_run.py:1199` |
| 24 | `dry_run_q1_trend_launch_min_score` | 5 | `scripts/audit_q1_trend_launch_hits.py:86`<br>`scripts/run_live_dry_run.py:584`<br>`scripts/run_live_dry_run.py:1195`<br>`scripts/verify_q1_trend_launch_fix.py:149`<br>`scripts/verify_q1_trend_launch_fix.py:171` |
| 25 | `dry_run_rank_end` | 3 | `scripts/run_live_dry_run.py:2473`<br>`scripts/run_live_dry_run.py:2478`<br>`scripts/run_live_dry_run.py:2488` |
| 26 | `dry_run_rank_start` | 3 | `scripts/run_live_dry_run.py:2473`<br>`scripts/run_live_dry_run.py:2477`<br>`scripts/run_live_dry_run.py:2487` |
| 27 | `dry_run_symbol_source` | 1 | `scripts/run_live_dry_run.py:2471` |
| 28 | `dry_run_symbols` | 3 | `scripts/run_live_dry_run.py:2469`<br>`scripts/run_live_dry_run.py:2484`<br>`scripts/run_live_dry_run.py:2492` |
| 29 | `dry_run_warmup_15m_bars` | 6 | `scripts/run_live_dry_run.py:142`<br>`scripts/run_live_dry_run.py:198`<br>`scripts/run_live_dry_run.py:475`<br>`scripts/run_live_dry_run.py:2764`<br>`scripts/run_live_dry_run.py:2787` |
| 30 | `ema200_gate_mode` | 4 | `scripts/run_live_dry_run.py:2640`<br>`scripts/run_live_dry_run.py:2871`<br>`scripts/run_offline_backtest.py:310`<br>`src/signals/entry_chain.py:372` |
| 31 | `ema50_min_for_direct` | 1 | `src/signals/entry_chain.py:391` |
| 32 | `ema50_min_for_probe` | 1 | `src/signals/entry_chain.py:395` |
| 33 | `enable_long_context_discounts` | 2 | `src/signals/entry_chain.py:141`<br>`src/signals/entry_chain.py:328` |
| 34 | `experiment_daily_loss_limit` | 2 | `scripts/run_live_dry_run.py:611`<br>`scripts/run_live_dry_run.py:1814` |
| 35 | `experiment_war_fund_loss_limit` | 3 | `scripts/run_live_dry_run.py:610`<br>`scripts/run_live_dry_run.py:1426`<br>`scripts/run_live_dry_run.py:1813` |
| 36 | `fib_min_direct_score` | 1 | `src/signals/entry_chain.py:445` |
| 37 | `high_vol_atr_pct` | 1 | `src/signals/entry_chain_scoring.py:87` |
| 38 | `leverage_5x_cci_min` | 1 | `src/signals/entry_chain.py:649` |
| 39 | `leverage_5x_fib_min` | 1 | `src/signals/entry_chain.py:647` |
| 40 | `leverage_5x_pa_min` | 1 | `src/signals/entry_chain.py:648` |
| 41 | `leverage_5x_rr_min` | 1 | `src/signals/entry_chain.py:650` |
| 42 | `long_chase_trigger_mult` | 1 | `src/signals/entry_chain.py:338` |
| 43 | `long_chase_watch_enabled` | 1 | `src/signals/entry_chain.py:129` |
| 44 | `long_cvd_weak_mult` | 1 | `src/signals/entry_chain.py:341` |
| 45 | `long_cvd_weak_threshold` | 3 | `scripts/run_live_dry_run.py:2902`<br>`scripts/run_offline_backtest.py:338`<br>`src/signals/entry_chain.py:340` |
| 46 | `long_min_cvd_direct_score` | 1 | `src/signals/entry_chain.py:414` |
| 47 | `long_min_direction_direct_score` | 1 | `src/signals/entry_chain.py:411` |
| 48 | `long_min_quality_direct_score` | 1 | `src/signals/entry_chain.py:412` |
| 49 | `long_min_trigger_direct_score` | 1 | `src/signals/entry_chain.py:413` |
| 50 | `long_overextension_quality_mult` | 2 | `src/signals/entry_chain.py:331`<br>`src/signals/entry_chain.py:332` |
| 51 | `long_overextension_watch_enabled` | 1 | `src/signals/entry_chain.py:128` |
| 52 | `long_threshold_offset` | 4 | `scripts/replay_atom_chain.py:90`<br>`scripts/replay_symbol_chain.py:100`<br>`src/signals/entry_chain.py:302`<br>`src/signals/entry_chain.py:314` |
| 53 | `long_upper_wick_trigger_mult` | 1 | `src/signals/entry_chain.py:335` |
| 54 | `low_vol_atr_pct` | 1 | `src/signals/entry_chain_scoring.py:90` |
| 55 | `macro_daily_drop_block_pct` | 1 | `src/signals/entry_chain.py:145` |
| 56 | `macro_weekly_drop_block_pct` | 3 | `scripts/audit_entry_gate_controls.py:150`<br>`src/signals/entry_chain.py:233`<br>`src/signals/entry_chain_gates.py:44` |
| 57 | `margin_buffer_pct` | 4 | `scripts/audit_entry_gate_controls.py:240`<br>`src/signals/entry_chain.py:253`<br>`src/signals/entry_chain.py:731`<br>`src/signals/entry_chain_gates.py:64` |
| 58 | `max_active_symbols` | 5 | `scripts/audit_entry_gate_controls.py:166`<br>`scripts/audit_entry_gate_controls.py:237`<br>`scripts/run_live_dry_run.py:547`<br>`src/signals/entry_chain.py:241`<br>`src/signals/entry_chain_gates.py:52` |
| 59 | `max_high_beta_exposure_pct` | 2 | `src/signals/entry_chain.py:617`<br>`src/signals/entry_chain_gates.py:97` |
| 60 | `max_large_cap_exposure_pct` | 2 | `src/signals/entry_chain.py:613`<br>`src/signals/entry_chain_gates.py:93` |
| 61 | `max_mainstream_exposure_pct` | 4 | `src/signals/entry_chain.py:615`<br>`src/signals/entry_chain.py:618`<br>`src/signals/entry_chain_gates.py:95`<br>`src/signals/entry_chain_gates.py:98` |
| 62 | `max_same_direction_exposure_pct` | 6 | `scripts/audit_entry_gate_controls.py:191`<br>`scripts/audit_entry_gate_controls.py:239`<br>`scripts/run_live_dry_run.py:549`<br>`scripts/run_live_dry_run.py:953`<br>`src/signals/entry_chain.py:251` |
| 63 | `max_single_trade_risk_pct` | 2 | `src/signals/entry_chain.py:728`<br>`src/signals/entry_chain.py:737` |
| 64 | `max_stop_pct` | 10 | `scripts/run_live_dry_run.py:665`<br>`scripts/run_live_dry_run.py:672`<br>`scripts/run_live_dry_run.py:2897`<br>`scripts/run_offline_backtest.py:333`<br>`src/backtest/engine.py:648` |
| 65 | `max_symbol_trades_per_day` | 4 | `scripts/audit_entry_gate_controls.py:176`<br>`scripts/run_live_dry_run.py:550`<br>`src/signals/entry_chain.py:245`<br>`src/signals/entry_chain_gates.py:56` |
| 66 | `max_total_exposure_pct` | 6 | `scripts/audit_entry_gate_controls.py:186`<br>`scripts/audit_entry_gate_controls.py:238`<br>`scripts/run_live_dry_run.py:548`<br>`scripts/run_live_dry_run.py:952`<br>`src/signals/entry_chain.py:249` |
| 67 | `min_cvd_direct_score` | 1 | `src/signals/entry_chain.py:406` |
| 68 | `min_cvd_probe_score` | 1 | `src/signals/entry_chain.py:385` |
| 69 | `min_daily_trades` | 3 | `scripts/run_live_dry_run.py:552`<br>`src/signals/entry_chain.py:268`<br>`src/signals/entry_chain_gates.py:75` |
| 70 | `min_direction_direct_score` | 1 | `src/signals/entry_chain.py:403` |
| 71 | `min_direction_probe_score` | 1 | `src/signals/entry_chain.py:382` |
| 72 | `min_quality_direct_score` | 1 | `src/signals/entry_chain.py:404` |
| 73 | `min_quality_probe_score` | 1 | `src/signals/entry_chain.py:383` |
| 74 | `min_stop_pct` | 10 | `scripts/run_live_dry_run.py:664`<br>`scripts/run_live_dry_run.py:671`<br>`scripts/run_live_dry_run.py:2897`<br>`scripts/run_offline_backtest.py:333`<br>`src/backtest/engine.py:647` |
| 75 | `min_trigger_direct_score` | 1 | `src/signals/entry_chain.py:405` |
| 76 | `min_trigger_probe_score` | 1 | `src/signals/entry_chain.py:384` |
| 77 | `mirror_ab_allowed_reasons` | 2 | `scripts/run_live_dry_run.py:595`<br>`scripts/run_live_dry_run.py:1986` |
| 78 | `mirror_ab_enabled` | 2 | `scripts/run_live_dry_run.py:592`<br>`scripts/run_live_dry_run.py:1976` |
| 79 | `mirror_ab_include_q1_watch` | 2 | `scripts/run_live_dry_run.py:596`<br>`scripts/run_live_dry_run.py:1989` |
| 80 | `mirror_ab_min_score` | 2 | `scripts/run_live_dry_run.py:593`<br>`scripts/run_live_dry_run.py:1978` |
| 81 | `mirror_ab_mode` | 1 | `scripts/run_live_dry_run.py:271` |
| 82 | `mirror_ab_notional` | 2 | `scripts/run_live_dry_run.py:594`<br>`scripts/run_live_dry_run.py:2009` |
| 83 | `mirror_ab_payoff_early_breakeven_trigger_r` | 1 | `scripts/run_live_dry_run.py:691` |
| 84 | `mirror_ab_payoff_pilot_enabled` | 2 | `scripts/run_live_dry_run.py:688`<br>`scripts/run_live_dry_run.py:690` |
| 85 | `mirror_ab_payoff_trend_trigger_r` | 1 | `scripts/run_live_dry_run.py:688` |
| 86 | `observation_only_symbols` | 2 | `scripts/run_live_dry_run.py:1145`<br>`scripts/run_live_dry_run.py:2167` |
| 87 | `pa_min_direct_score` | 1 | `src/signals/entry_chain.py:444` |
| 88 | `paper_ab_auto_report_enabled` | 3 | `scripts/run_live_dry_run.py:597`<br>`scripts/run_live_dry_run.py:797`<br>`scripts/run_live_dry_run.py:818` |
| 89 | `paper_ab_auto_switch_enabled` | 4 | `scripts/run_live_dry_run.py:599`<br>`scripts/run_live_dry_run.py:736`<br>`scripts/run_live_dry_run.py:819`<br>`scripts/run_live_dry_run.py:863` |
| 90 | `paper_ab_auto_switch_min_closed_trades` | 3 | `scripts/run_live_dry_run.py:601`<br>`scripts/run_live_dry_run.py:821`<br>`scripts/run_live_dry_run.py:866` |
| 91 | `paper_ab_auto_switch_min_reports` | 4 | `scripts/run_live_dry_run.py:600`<br>`scripts/run_live_dry_run.py:820`<br>`scripts/run_live_dry_run.py:868`<br>`scripts/run_live_dry_run.py:880` |
| 92 | `paper_ab_auto_switch_payoff_mult` | 4 | `scripts/run_live_dry_run.py:602`<br>`scripts/run_live_dry_run.py:822`<br>`scripts/run_live_dry_run.py:881`<br>`scripts/run_live_dry_run.py:898` |
| 93 | `paper_ab_pure_ladder_enabled` | 3 | `scripts/analysis/verify_pure_ladder_arm.py:70` |
| 94 | `paper_ab_report_closed_trade_interval` | 2 | `scripts/run_live_dry_run.py:598`<br>`scripts/run_live_dry_run.py:801` |
| 95 | `paper_exit_mode` | 4 | `scripts/run_live_dry_run.py:559`<br>`scripts/run_live_dry_run.py:668`<br>`scripts/run_live_dry_run.py:738`<br>`scripts/run_live_dry_run.py:2441` |
| 96 | `paper_exit_trailing_r_mult` | 3 | `scripts/run_live_dry_run.py:561`<br>`scripts/run_live_dry_run.py:670`<br>`scripts/run_live_dry_run.py:689` |
| 97 | `paper_exit_trend_trigger_r` | 3 | `scripts/run_live_dry_run.py:560`<br>`scripts/run_live_dry_run.py:669`<br>`scripts/run_live_dry_run.py:688` |
| 98 | `portfolio_daily_loss_circuit_enabled` | 1 | `scripts/run_live_dry_run.py:2307` |
| 99 | `portfolio_daily_loss_limit` | 1 | `scripts/run_live_dry_run.py:2313` |
| 100 | `portfolio_stop_circuit_count` | 1 | `scripts/run_live_dry_run.py:2290` |
| 101 | `portfolio_stop_circuit_enabled` | 1 | `scripts/run_live_dry_run.py:2288` |
| 102 | `portfolio_stop_circuit_hours` | 1 | `scripts/run_live_dry_run.py:2291` |
| 103 | `post_initial_stop_cooldown_enabled` | 1 | `scripts/run_live_dry_run.py:2246` |
| 104 | `post_initial_stop_cooldown_hours` | 1 | `scripts/run_live_dry_run.py:2248` |
| 105 | `probe_conditions` | 4 | `scripts/run_live_dry_run.py:1535`<br>`src/signals/entry_chain.py:136`<br>`src/signals/entry_chain.py:309`<br>`src/signals/entry_chain.py:465` |
| 106 | `probe_liquidity_ratio` | 1 | `src/signals/entry_chain.py:154` |
| 107 | `probe_risk_pct` | 2 | `scripts/run_live_dry_run.py:546`<br>`src/signals/entry_chain.py:723` |
| 108 | `probe_threshold` | 3 | `scripts/audit_entry_gate_controls.py:263`<br>`scripts/vps_dry_run_healthcheck.py:36`<br>`src/signals/entry_chain.py:288` |
| 109 | `quadrant_cci_min` | 5 | `scripts/diagnose_scout_mission_reachability.py:62`<br>`scripts/replay_atom_chain.py:128`<br>`scripts/replay_symbol_chain.py:145`<br>`scripts/run_live_dry_run.py:569`<br>`scripts/run_live_dry_run.py:1624` |
| 110 | `quadrant_flow_cvd_min` | 5 | `scripts/diagnose_scout_mission_reachability.py:61`<br>`scripts/replay_atom_chain.py:127`<br>`scripts/replay_symbol_chain.py:144`<br>`scripts/run_live_dry_run.py:568`<br>`scripts/run_live_dry_run.py:1623` |
| 111 | `quadrant_pending_state_enabled` | 3 | `scripts/run_live_dry_run.py:177`<br>`scripts/run_live_dry_run.py:477`<br>`scripts/run_live_dry_run.py:582` |
| 112 | `quadrant_price_action_min` | 5 | `scripts/diagnose_scout_mission_reachability.py:60`<br>`scripts/replay_atom_chain.py:126`<br>`scripts/replay_symbol_chain.py:143`<br>`scripts/run_live_dry_run.py:567`<br>`scripts/run_live_dry_run.py:1620` |
| 113 | `quadrant_trend_ema_min` | 5 | `scripts/diagnose_scout_mission_reachability.py:59`<br>`scripts/replay_atom_chain.py:125`<br>`scripts/replay_symbol_chain.py:142`<br>`scripts/run_live_dry_run.py:566`<br>`scripts/run_live_dry_run.py:1619` |
| 114 | `regime_overlay` | 5 | `scripts/run_live_dry_run.py:243`<br>`scripts/run_live_dry_run.py:368`<br>`scripts/run_live_dry_run.py:2677` |
| 115 | `rolling_symbol_cooldown_enabled` | 1 | `scripts/run_live_dry_run.py:2267` |
| 116 | `rolling_symbol_cooldown_hours` | 1 | `scripts/run_live_dry_run.py:2270` |
| 117 | `rolling_symbol_cooldown_stop_threshold` | 1 | `scripts/run_live_dry_run.py:2277` |
| 118 | `rolling_symbol_cooldown_window_hours` | 1 | `scripts/run_live_dry_run.py:2269` |
| 119 | `rr_min_direct_score` | 1 | `src/signals/entry_chain.py:446` |
| 120 | `scout_micro_allow_degraded_data` | 2 | `scripts/run_live_dry_run.py:615`<br>`scripts/run_live_dry_run.py:1349` |
| 121 | `scout_micro_exit_mode` | 2 | `scripts/run_live_dry_run.py:562`<br>`scripts/run_live_dry_run.py:661` |
| 122 | `scout_micro_exit_trailing_r_mult` | 2 | `scripts/run_live_dry_run.py:564`<br>`scripts/run_live_dry_run.py:663` |
| 123 | `scout_micro_exit_trend_trigger_r` | 2 | `scripts/run_live_dry_run.py:563`<br>`scripts/run_live_dry_run.py:662` |
| 124 | `scout_micro_fib_continuation_min_cvd_score` | 2 | `scripts/diagnose_scout_mission_reachability.py:125`<br>`scripts/run_live_dry_run.py:1523` |
| 125 | `scout_micro_fib_continuation_min_ema_score` | 2 | `scripts/diagnose_scout_mission_reachability.py:124`<br>`scripts/run_live_dry_run.py:1522` |
| 126 | `scout_micro_fib_continuation_min_pa_score` | 2 | `scripts/diagnose_scout_mission_reachability.py:126`<br>`scripts/run_live_dry_run.py:1524` |
| 127 | `scout_micro_fib_continuation_min_score` | 2 | `scripts/diagnose_scout_mission_reachability.py:123`<br>`scripts/run_live_dry_run.py:1521` |
| 128 | `scout_micro_high_score_long_offset_min_cvd_score` | 3 | `scripts/diagnose_high_score_long_offset_probe.py:69`<br>`scripts/diagnose_scout_mission_reachability.py:117`<br>`scripts/run_live_dry_run.py:1510` |
| 129 | `scout_micro_high_score_long_offset_min_fib_score` | 3 | `scripts/diagnose_high_score_long_offset_probe.py:68`<br>`scripts/diagnose_scout_mission_reachability.py:116`<br>`scripts/run_live_dry_run.py:1509` |
| 130 | `scout_micro_high_score_long_offset_min_pa_score` | 3 | `scripts/diagnose_high_score_long_offset_probe.py:67`<br>`scripts/diagnose_scout_mission_reachability.py:115`<br>`scripts/run_live_dry_run.py:1508` |
| 131 | `scout_micro_high_score_long_offset_min_rr_score` | 3 | `scripts/diagnose_high_score_long_offset_probe.py:70`<br>`scripts/diagnose_scout_mission_reachability.py:118`<br>`scripts/run_live_dry_run.py:1511` |
| 132 | `scout_micro_high_score_long_offset_min_score` | 3 | `scripts/diagnose_high_score_long_offset_probe.py:66`<br>`scripts/diagnose_scout_mission_reachability.py:114`<br>`scripts/run_live_dry_run.py:1507` |
| 133 | `scout_micro_high_score_long_offset_quadrants` | 3 | `scripts/diagnose_high_score_long_offset_probe.py:94`<br>`scripts/diagnose_scout_mission_reachability.py:111`<br>`scripts/run_live_dry_run.py:1497` |
| 134 | `scout_micro_initial_stop_cooldown_hours` | 1 | `scripts/run_live_dry_run.py:1563` |
| 135 | `scout_micro_leverage` | 2 | `scripts/run_live_dry_run.py:1914`<br>`scripts/run_live_dry_run.py:1936` |
| 136 | `scout_micro_min_score` | 1 | `scripts/run_live_dry_run.py:1360` |
| 137 | `scout_micro_mission_stop_circuit_count` | 2 | `scripts/run_live_dry_run.py:613`<br>`scripts/run_live_dry_run.py:1585` |
| 138 | `scout_micro_mission_stop_circuit_enabled` | 3 | `scripts/run_live_dry_run.py:612`<br>`scripts/run_live_dry_run.py:1414`<br>`scripts/run_live_dry_run.py:1583` |
| 139 | `scout_micro_mission_stop_circuit_hours` | 2 | `scripts/run_live_dry_run.py:614`<br>`scripts/run_live_dry_run.py:1586` |
| 140 | `scout_micro_notional` | 1 | `scripts/run_live_dry_run.py:1897` |
| 141 | `scout_micro_q1_rr_gap_enabled` | 3 | `scripts/diagnose_scout_mission_reachability.py:107`<br>`scripts/run_live_dry_run.py:571`<br>`scripts/run_live_dry_run.py:1650` |
| 142 | `scout_micro_q1_rr_gap_min_cvd_score` | 2 | `scripts/run_live_dry_run.py:573`<br>`scripts/run_live_dry_run.py:1658` |
| 143 | `scout_micro_q1_rr_gap_min_score` | 2 | `scripts/run_live_dry_run.py:572`<br>`scripts/run_live_dry_run.py:1657` |
| 144 | `scout_micro_q2_pending_confirm_bars` | 2 | `scripts/run_live_dry_run.py:580`<br>`scripts/run_live_dry_run.py:1714` |
| 145 | `scout_micro_q2_pending_confirm_cci_score` | 2 | `scripts/run_live_dry_run.py:581`<br>`scripts/run_live_dry_run.py:1777` |
| 146 | `scout_micro_q2_pending_enabled` | 5 | `scripts/diagnose_scout_mission_reachability.py:99`<br>`scripts/run_live_dry_run.py:577`<br>`scripts/run_live_dry_run.py:1672`<br>`scripts/run_live_dry_run.py:1703`<br>`scripts/run_live_dry_run.py:1763` |
| 147 | `scout_micro_q2_pending_min_pa_score` | 3 | `scripts/counterfactual_q2_pending.py:50`<br>`scripts/run_live_dry_run.py:579`<br>`scripts/run_live_dry_run.py:1712` |
| 148 | `scout_micro_q2_pending_min_score` | 4 | `scripts/counterfactual_q2_pending.py:49`<br>`scripts/run_live_dry_run.py:249`<br>`scripts/run_live_dry_run.py:578`<br>`scripts/run_live_dry_run.py:1710` |
| 149 | `scout_micro_q3_to_q1_confirm_bars` | 2 | `scripts/run_live_dry_run.py:576`<br>`scripts/run_live_dry_run.py:1691` |
| 150 | `scout_micro_q3_to_q1_confirm_pa_score` | 1 | `scripts/run_live_dry_run.py:1746` |
| 151 | `scout_micro_q3_to_q1_enabled` | 5 | `scripts/diagnose_scout_mission_reachability.py:103`<br>`scripts/run_live_dry_run.py:574`<br>`scripts/run_live_dry_run.py:1664`<br>`scripts/run_live_dry_run.py:1680`<br>`scripts/run_live_dry_run.py:1732` |
| 152 | `scout_micro_q3_to_q1_min_cvd_score` | 1 | `scripts/run_live_dry_run.py:1689` |
| 153 | `scout_micro_q3_to_q1_min_score` | 2 | `scripts/run_live_dry_run.py:575`<br>`scripts/run_live_dry_run.py:1687` |
| 154 | `scout_micro_reversal_pivot_enabled` | 3 | `scripts/diagnose_scout_mission_reachability.py:89`<br>`scripts/run_live_dry_run.py:616`<br>`scripts/run_live_dry_run.py:1465` |
| 155 | `scout_micro_reversal_pivot_max_cci_score` | 3 | `scripts/diagnose_scout_mission_reachability.py:96`<br>`scripts/run_live_dry_run.py:619`<br>`scripts/run_live_dry_run.py:1478` |
| 156 | `scout_micro_reversal_pivot_max_cvd_score` | 3 | `scripts/diagnose_scout_mission_reachability.py:95`<br>`scripts/run_live_dry_run.py:618`<br>`scripts/run_live_dry_run.py:1477` |
| 157 | `scout_micro_reversal_pivot_min_score` | 3 | `scripts/diagnose_scout_mission_reachability.py:91`<br>`scripts/run_live_dry_run.py:617`<br>`scripts/run_live_dry_run.py:1470` |
| 158 | `scout_micro_reversal_pivot_notional` | 2 | `scripts/run_live_dry_run.py:620`<br>`scripts/run_live_dry_run.py:1897` |
| 159 | `scout_micro_rr_gap_block_symbols` | 1 | `scripts/run_live_dry_run.py:1449` |
| 160 | `scout_micro_same_side_cooldown_hours` | 1 | `scripts/run_live_dry_run.py:1568` |
| 161 | `scout_micro_scout_only_min_fib_score` | 4 | `scripts/diagnose_scout_mission_reachability.py:132`<br>`scripts/diagnose_scout_mission_reachability.py:139`<br>`scripts/run_live_dry_run.py:1537`<br>`scripts/run_live_dry_run.py:1548` |
| 162 | `scout_micro_scout_only_min_pa_score` | 4 | `scripts/diagnose_scout_mission_reachability.py:133`<br>`scripts/diagnose_scout_mission_reachability.py:140`<br>`scripts/run_live_dry_run.py:1538`<br>`scripts/run_live_dry_run.py:1549` |
| 163 | `scout_micro_scout_only_min_rr_score` | 4 | `scripts/diagnose_scout_mission_reachability.py:134`<br>`scripts/diagnose_scout_mission_reachability.py:141`<br>`scripts/run_live_dry_run.py:1539`<br>`scripts/run_live_dry_run.py:1550` |
| 164 | `scout_micro_scout_only_min_score` | 2 | `scripts/diagnose_scout_mission_reachability.py:138`<br>`scripts/run_live_dry_run.py:1547` |
| 165 | `scout_micro_scout_only_symbols` | 2 | `scripts/diagnose_scout_mission_reachability.py:137`<br>`scripts/run_live_dry_run.py:1544` |
| 166 | `scout_micro_symbols` | 2 | `scripts/run_live_dry_run.py:1347`<br>`scripts/run_live_dry_run.py:2115` |
| 167 | `scout_micro_targeted_long_symbols` | 3 | `scripts/diagnose_high_score_long_offset_probe.py:65`<br>`scripts/diagnose_scout_mission_reachability.py:110`<br>`scripts/run_live_dry_run.py:1495` |
| 168 | `scout_micro_watch_only_promotion_min_score` | 2 | `scripts/diagnose_scout_mission_reachability.py:131`<br>`scripts/run_live_dry_run.py:1533` |
| 169 | `short_min_cvd_direct_score` | 1 | `src/signals/entry_chain.py:424` |
| 170 | `short_min_direction_direct_score` | 1 | `src/signals/entry_chain.py:421` |
| 171 | `short_min_quality_direct_score` | 1 | `src/signals/entry_chain.py:422` |
| 172 | `short_min_trigger_direct_score` | 1 | `src/signals/entry_chain.py:423` |
| 173 | `short_threshold_offset` | 2 | `src/signals/entry_chain.py:304`<br>`src/signals/entry_chain.py:316` |
| 174 | `use_ema_architecture` | 10 | `scripts/run_live_dry_run.py:155`<br>`scripts/run_live_dry_run.py:2639`<br>`scripts/run_live_dry_run.py:2787`<br>`scripts/run_live_dry_run.py:2870`<br>`scripts/run_offline_backtest.py:309` |
| 175 | `use_fib_pa_architecture` | 14 | `scripts/run_live_dry_run.py:155`<br>`scripts/run_live_dry_run.py:2610`<br>`scripts/run_live_dry_run.py:2641`<br>`scripts/run_live_dry_run.py:2872`<br>`scripts/run_live_dry_run.py:2875` |
| 176 | `watch_only_symbols` | 7 | `scripts/audit_entry_gate_controls.py:139`<br>`scripts/audit_entry_gate_controls.py:140`<br>`scripts/audit_entry_gate_controls.py:236`<br>`scripts/diagnose_scout_mission_reachability.py:129`<br>`scripts/run_live_dry_run.py:1143` |
| 177 | `watch_threshold` | 4 | `scripts/audit_entry_gate_controls.py:264`<br>`scripts/replay_atom_chain.py:89`<br>`scripts/replay_symbol_chain.py:99`<br>`src/signals/entry_chain.py:289` |
| 178 | `weak_edge_direct_max_score` | 1 | `scripts/run_live_dry_run.py:2324` |
| 179 | `weak_edge_direct_min_score` | 1 | `scripts/run_live_dry_run.py:2324` |
| 180 | `weak_edge_probe_max_score` | 1 | `scripts/run_live_dry_run.py:2338` |
| 181 | `weak_edge_probe_min_score` | 1 | `scripts/run_live_dry_run.py:2338` |

## UNKNOWN_KEY(共 0 个)

(无,所有配置键都在数据类中声明)

## 扫描口径

- 扫描根: `src/**/*.py`, `scripts/**/*.py`
- 排除: `src/signals/entry_chain_config.py`、`__pycache__/`、`tests/`
- 配置来源: `entry_chain.dry_run - 副本.json`, `entry_chain.dry_run_aggressive.json`, `entry_chain.dry_run_balanced.json`, `entry_chain.dry_run_conservative.json`, `entry_chain.dry_run_ema_hard.json`, `entry_chain.dry_run_ema_soft.json`, `entry_chain.dry_run_ema_soft_lifecycle_hardened.json`, `entry_chain.dry_run_fib_pa_v1.json`, `entry_chain.dry_run_fib_pa_v12.json`, `entry_chain.dry_run_highest_win.json`, `entry_chain.dry_run_no_rsi.json`, `entry_chain.dry_run_regime_shadow.json`, `entry_chain.dry_run_risk_first.json`, `entry_chain.dry_run_s1_shadow.json`, `entry_chain.dry_run_v4_side_split.json`, `entry_chain.dry_run_v4_side_symbol_bucket.json`, `entry_chain.dry_run_v5_long_context_discount.json`, `entry_chain.dry_run_v5_symbol_bucket_long_context.json`, `entry_chain.dry_run_v5_symbol_bucket_only.json`
- 读取点判定规则:
  - Attribute: <holder>.<field> 且 holder 标识符以 cfg/config 结尾 -> LIVE_READ
  - Call: <holder>.get("<field>") -> LIVE_READ
  - Subscript: <any>["<field>"] -> LIVE_READ(不校验持有者)
  - Call: getattr(<holder>, "<field>", ...) -> DYNAMIC_READ
  - Call: vars(<holder>).get("<field>") -> DYNAMIC_READ
