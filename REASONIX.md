# REASONIX.md — AI300 多周期趋势交易系统

Binance USDT 永续(市值前 20 币)多周期趋势交易系统:四象限评分决策链 + dry-run/paper 优先运行。当前 VPS 以 dry-run 模式运行(aggressive tier),无实盘挂单;2026-09-27 起并行记录五正交因子影子数据(不影响决策)。

## Project
- 规格文档:`docs/00_project_overview.md` 起(编号规格);中文
- 入口:`scripts/run_live_dry_run.py`(约 129KB,主 dry-run 循环)
- 运行时依赖仅 `requests`/`urllib3`;测试用 `pytest`(`pytest.ini` 已配 `pythonpath = .`)
- VPS 部署:`deploy/systemd/ai300-dry-run.service`(WorkingDirectory=/root/AIBOT,venv python)

## Commands
- 测试:`python -m pytest tests/ -q`(当前 723 passed + 1 个既有无关失败:`test_describe_indicator_rules` EMA/RSI 契约漂移)
- 聚焦:`python -m pytest tests/test_<module>.py -q`
- 主循环(dry-run):
  `python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json --target-tier aggressive --market-data-source public-binance --log-root logs --align-to-kline-close --post-close-delay-seconds 5`
  加 `--market-data-source synthetic --once` 可本地单轮跑通(不依赖外网)
- 回测:`python scripts/run_offline_backtest.py`、`python scripts/run_rolling_backtest.py`
- 数据下载:`python scripts/download_latest_30d_market_data.py`
- 部署后验证:`python scripts/verify_q1_trend_launch_fix.py --mode online --log-root logs --hours 24`、`python scripts/evaluate_offense_fixes.py`
- 五因子正交性验收:`python scripts/verify_five_factor_orthogonality.py --start <日期> --end <日期>`(报告落 `logs/analysis/five-factor-orthogonality/`)
- 建议追踪:`python scripts/recommendation_tracker.py list|check|show`(check 返回码 1 = 有未解决 P0)
- 配置审计:`python scripts/audit_duplicate_json_keys.py [文件]`

## Architecture
- `scripts/run_live_dry_run.py`:主循环——评分 → 四象限标注(Q1-Q4)→ 闸门(gate_rejections)→ near-miss → SCOUT 侦察 → A/B mirror 实验 → 纸面账本
- `src/signals/entry_chain*.py`:核心决策链(`entry_chain.py` 链逻辑、`entry_chain_config.py` 配置类、`entry_chain_features.py` 特征、`entry_chain_gates.py` 闸门、`entry_chain_scoring.py` 评分)
- `src/signals/orthogonal_factors.py`:五正交因子 F1-F5(trend_persistence / structure_location / payoff_geometry / volatility_regime / order_flow),**P0 影子专用**
- `src/observability/`:纸面账本(`paper_trading.py` 主/SCOUT/A-B 三套)、`dry_run_summary.py`(summary.json)、`decision_audit.py`(各 JSONL 的唯一写入口)
- `src/indicators/` + `src/api/binance_client.py`:指标引擎(EMA/RSI/CCI/CVD/Fib/PA)与 Binance 行情
- `src/risk/`:仓位(`position_sizer.py`)、止损、组合敞口(`net_beta_exposure_model.py`)
- `src/backtest/`:回测引擎(offline/rolling),与 dry-run 同构;`BacktestBar.taker_buy_volume` 源自 klines 第 10 列,是 F5 订单流的数据入口
- 数据流:`logs/<UTC日>/decisions.jsonl`、`near_misses.jsonl`、`scout_decisions.jsonl`、`gate_rejections.jsonl`、`paper_trades.jsonl`、`summary.json`、`scout_micro/`、`paper_ab/{legacy,trend_capture}/`;`decisions.jsonl` 另含 P0 影子字段 `component_points_v2` + `component_points_v2_meta`

## Conventions
- 时间口径:日志/数据用真实 UTC;报告与分析用北京时间(UTC+8)。`decisions.jsonl` 顶层 `timestamp`=决策时刻,`kline.timestamp`=K线开盘;按日归档用顶层 timestamp
- 日志滚动:`logs/2026-08/2026-08-04/runtime.out.HH.log`(6h 一段);summary.json 为"进程重启后累计"滚动口径,分析一律直接读 JSONL 过滤
- 盈亏口径:账户实际盈亏看 `notional_pnl`/`position_realized_pnl`;`margin_pnl` 是保证金报告口径(杠杆放大),两者不可混用
- 测试纪律:新逻辑必须带 pytest 单测;配置改动同步更新 `tests/test_dry_run_configs.py` 断言
- 交付纪律:进攻/风控改动先经 dry-run/paper/SCOUT/A-B 验证;禁止全局放宽 RR 几何门槛、禁止解除黑名单(ZEC/XRP);新通道先进独立实验账本
- 小样本纪律:`<10` 笔不判定"有效/提炼特征",`<20` 笔不调参、不资源倾斜(见 `channel_cumulative_tracker.py` 常量)
- 建议闭环:轮次报告落 `docs/`(中文),状态记入 `docs/recommendations_tracking.md`,开篇跑 `recommendation_tracker.py check`;完成后状态改 DEPLOYED/VERIFIED
- 部署:本地交付 + 用户同步 VPS(`docs/runbooks/offense-fix-deploy.md`),systemd 重启后需跑在线验证脚本
- git:分支按日期命名(`08-04-00per`、`09-27-5factor`);直连 github.com 不通时用 `git -c http.proxy=http://127.0.0.1:12334 push`
- `.gitignore` 忽略 `logs/`、`/data/`、`/reports/`、`.superpowers/`、`.env`、密钥类;未忽略但**勿提交**:`.reasonix/`、`.pytest_tmp_*`、`docs/80-07-00.txt`(历史遗留)
- 分析脚本放 `scripts/`,中间产出放 `logs/analysis/`(git-ignored);交付模式禁止内联 `python -c`

## Notes
- **五正交因子 P0 影子(2026-09-27 起)**:`orthogonal_factors.py` 的 F1-F5 仅在 `run_live_dry_run.py::attach_five_factor_shadow` 中写入 `decisions.jsonl` 记录字段,**不参与 total_score / 象限 / 通道门槛 / 杠杆 / action**。`tests/test_five_factor_shadow_readonly.py` 用源码级断言强制该契约(决策层不得出现 `component_points_v2`)。回滚 = 配置 `five_factor_shadow_enabled: false`。旧六因子与旧函数全部保留(P0 是并列而非替换),切换在 P4。设计与裁决见 `docs/2026-09-27-five-orthogonal-factor-strategy-decision.md`、实施记录见 `docs/2026-09-27-five-factor-p0-shadow-implementation.md`
- F4 波动率分位受 `--public-kline-limit`(默认 240)限制,实际回看约 2.5 天而非设计的 30 天,具体值见 `component_points_v2_meta.volatility_lookback_days`;**不得为提高该窗口调大取数**——会增加 15m 历史从而改变 EMA200,进而改变旧评分(违反 P0 红线)
- 进攻配置通道现状:`q1_green_channel` / `q1_trend_launch` / `q2_pending` / `q3_to_q1` 启用;`reversal_pivot` 与 `q1_rr_gap` 停用(保持 false);`mirror_ab` 为 `shadow_only`(记录但不计敞口/熔断)
- 主账本零开仓的根因曾是 `_q1_trend_launch_eligible` 的确认标签死门槛(已修复,commit 2e64232+2ac62df);LONG 侧 `long_threshold_offset` 为有意两层偏移(probe_conditions 7.0 / 顶层 10.0),勿删
- 主账本交易的可观测性:`paper_trading.py::_resolve_entry_channel` 保证 `entry_channel` 非 null(缺失时 DIRECT→`main_direct` / PROBE→`main_probe`)
