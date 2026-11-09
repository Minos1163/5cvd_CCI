# AI300 策略优化建议与研究执行方案
**文档版本：** V1.0  
**依据材料：** `亏损归因报告：2026-10-31 重启 → 2026-11-08`、`AI300 策略指标因子与决策逻辑 · 评审稿（2026-11-08）`  
**用途：** 作为下一轮策略审查、实验设计和 Codex 工程任务的依据  
**状态：** 研究建议，不构成实盘批准  
**原则：** 先统一事实与口径，再修复决策链，再验证策略优势，最后讨论执行部署

---

## 0. 结论先行
### 0.1 核心判断
1. 本窗口 MAIN 主账本不是净亏损，而是净盈利 `+33.762404 USDT`。；2. 这笔净盈利高度依赖单笔 `NEARUSDT SHORT`，该笔贡献约占全窗口净额的 `97.59%`。；3. 剔除该笔后，MAIN 主账本净额仅约 `+0.813862 USDT`。；4. 本窗口只有 `11` 笔完整平仓交易，其中 `3` 笔盈利、`8` 笔亏损，胜率为 `27.27%`。；5. 名义样本 `n=11`，按报告采用的同币同 UTC 日聚类后 `n_eff=9`，不足以确认稳定 alpha。
6. 报告中的 Wilson 区间、打平胜率和二项检验均不能支持明确的策略有效性结论。；7. 现有成本合计约 `14.666576 USDT`，约占净盈利的 `43.44%`，成本拖累不可忽视。；8. 不能把四套独立模拟账本相加成一个组合收益，也不能把杠杆放大的 margin PnL 当作权威收益。；9. 当前实跑配置与 systemd、README 类文档描述的配置存在漂移，降低了实验可复现性。；10. 当前 live 决策链并不是“指标规格文档”所暗示的完整指标组合，实际运行架构与规格声明之间存在明显差异。
11. 当前评分、四象限、通道替换、硬闸门、风险观察项和影子因子并非一个简单、单一的决策链，需要先明确唯一决策权。；12. 主账本和离线回测模拟器的 TP1 与最大持仓时间参数不同，回测结果不能未经校准就外推到当前 paper 主账本行为。；13. 下一轮最优先工作不是提高杠杆，也不是继续添加更多指标，而是统一配置、统一账本、统一退出参数和统一决策语义。；14. 在这些问题完成前，不应把本窗口的正收益当作可上线的策略证据。
### 0.2 建议总路线
- P0：建立唯一运行事实源，消除配置和运行漂移。；P0：统一 PnL、账本、交易数、暴露和持仓统计口径。；P0：明确唯一有效评分架构，清理死配置和未接线指标。；P0：明确主决策链与 `q1_green_channel` 的关系，禁止隐式替换。
- P1：先研究早期止损、交易集中度和成本侵蚀，不急于修改 TP 参数。；P1：拆分多空表现，但先做证据积累，不直接凭 4 笔多头样本调参。；P1：把主账本与回测模拟器的生命周期参数统一。；P2：对通道、象限、出场模式和配置版本进行成对、单变量实验。
- P2：建立滚动窗口、块 bootstrap 和样本量门槛。；P3：只有通过离线、paper、压力测试后，才讨论小规模真实执行验证。
### 0.3 不建议的动作
- 不因单笔 NEAR 大额盈利就放大仓位。；不为了追求 80% 胜率而强行提高门槛或删除亏损样本。；不因为 30 天回报不足就直接提高 4x、5x 杠杆。；不同时修改信号、止损、止盈、仓位和 Universe。
- 不把影子因子或 observation-only 模型描述成已经生效的风控。；不把独立实验账本的统计混成 MAIN 账本表现。；不依据 11 笔交易对单一指标、通道或象限做永久性结论。

---

## 1. 证据口径与分析边界
### 1.1 本文采用的证据级别
- **已核实事实：** 两份材料明确列出来源、字段、代码路径或可复算数据。；**推算：** 根据已核实输入，使用文中公式计算得到。；**研究线索：** 单一窗口、单一维度或小样本表现提示的方向。；**待验证假设：** 必须通过新实验验证，不得作为既成事实。
- **优化建议：** 未来版本可实施的策略或工程变更。
### 1.2 研究范围
1. 当前窗口为 2026-10-31 重启至 2026-11-08 的 paper dry-run 结果。；2. 运行模式是公开 Binance 行情与模拟成交，不是真实订单成交。；3. 所有账本均为独立模拟，不能直接相加形成组合账户。；4. 代码评审材料以 git HEAD `73388a5`、分支 `20261031-v2` 及报告注明的工作树状态为参照。；5. 部分文档、服务单元和实跑命令并不一致，必须保留这一限制。
6. 本文不是对未提供源码的独立审计，不会假设未展示的机制一定存在。
### 1.3 PnL 权威口径
1. 本窗口策略收益以 `net_pnl_full` 为主。；2. `net_pnl_full` 已扣除出场成本，并摊分对应入场成本。；3. `net_pnl` 属 close-only 口径，不应替代全成本收益。；4. `realized_margin_pnl` 带有 `deprecated_leverage_double_count` 标记，不得作为策略收益结论。；5. 对仓位级收益，应按 `position_id` 聚合所有 `PAPER_CLOSE` 与 `PAPER_REDUCE` 事件。
6. 不可把每天累计的 `realized_notional_pnl` 再相加。；7. 四个 paper ledger 是独立回放，不是四个可合并的真实子账户。；8. 所有报告必须写明 `pnl_schema_version` 与 `pnl_accounting_mode`。
### 1.4 配置口径
1. 实跑配置应以启动日志中的 config 路径为准，而不是 README 或 systemd 注释。；2. 实跑 `target_tier=conservative`，而部分文档声称 aggressive。；3. 实跑 `post_close_delay=10s`，而部分服务文件声称 `5s`。；4. 实跑 config 是 `dry_run_regime_shadow.json`，而其他文档引用 `highest_win.json` 或 `fib_pa_v1.json`。；5. 实跑 universe 为 market-cap-rank 动态解析的 14 个标的；配置中的 `dry_run_symbols` 成员并不相同。
6. CLI `--symbols` 优先于 config `dry_run_symbols`，该优先级必须显式进入运行清单。；7. 配置文件内容不等于运行时一定生效，必须同时存在读取路径与运行日志证据。
### 1.5 禁止混淆的三件事
- 配置中声明了某个参数，不代表代码读取它。；代码存在某个函数，不代表实盘主循环调用它。；日志中记录某个字段，不代表它参与了决策或风险拦截。

---

## 2. 当前策略的真实问题排序
### 2.1 第一问题：盈利集中度过高
1. MAIN 账本期末净额为 `+33.762404 USDT`。；2. NEAR 空单净贡献为 `+32.948542 USDT`。；3. 该笔占净额约 `97.59%`。；4. 剔除该笔后净额约 `+0.813862 USDT`。；5. 前两笔盈利约占总盈利 `98.70%`。
6. `HHI(|net_pnl|)` 约为 `0.3915`，明显高于 11 笔均匀贡献的基准 `0.0909`。；7. 这说明账面正收益对少数大额赢家高度敏感。；8. 这不能单独证明策略无效，但足以阻止把该窗口称为稳健盈利证明。；9. 后续报告必须增加“剔除最大赢家”和“剔除前两大赢家”的敏感性结果。；10. 任何优化都要观察去除最大赢家后的净收益、PF 和期望值。
### 2.2 第二问题：样本量不足
1. 完整平仓交易只有 11 笔。；2. 盈利交易 3 笔，亏损交易 8 笔。；3. 名义胜率为 `27.27%`。；4. 按同 symbol 同 UTC 日聚类得到 `n_eff=9`。；5. 聚类后 Wilson 95% 区间仍覆盖打平胜率。
6. 块长敏感性和 block bootstrap 尚未执行。；7. 不能把名义 `n=11` 当成 11 个完全独立样本。；8. 不能因为 PF 达到 3.91 就忽略样本量问题。；9. 高 payoff 与低胜率可以共同产生正收益，但必须验证右尾是否可重复。；10. 研究阶段应优先扩大独立样本，而不是继续寻找只适合这 11 笔交易的阈值。
### 2.3 第三问题：运行口径漂移
1. 实跑配置、systemd 配置、REASONIX 文档和 CODEBUDDY 文档不一致。；2. 运行中的标的列表与 config 静态列表不一致。；3. 运行中的动态 Universe 来源与 CLI override 共同影响最终名单。；4. 当前窗口的实跑配置在报告中可以追溯，但文档不能单独复现。；5. 参数归因因此存在前提缺失。
6. 每一次研究运行都必须固化最终解析后的完整配置快照。；7. 每一次运行都必须记录完整 symbol snapshot。；8. 启动日志必须打印配置哈希、代码 commit、Universe 版本和 CLI 参数。；9. 服务文件和说明文档必须由同一个 deploy manifest 生成或校验。；10. 不允许再靠人工记忆判断 VPS 当时运行了哪一套配置。
### 2.4 第四问题：指标规格与 live 决策不一致
1. 指标规格层声明了 MACD、CCI、BOLL、EMA、CVD、ATR。；2. RSI 实现存在，但报告确认其没有进入 live 评分链。；3. 真正基于 taker-buy volume 的 CVD 计算存在于指标/规格路径，但 live 评分使用的是 candle-direction signed-volume 近似量。；4. 当前 live 评分链采用 fib_pa 架构，主要分量为 EMA context、CVD flow、CCI momentum、PA structure、Fibonacci location、RR geometry。；5. MACD 和 BOLL 在已提供 live 因子总表中没有被列为当前生效分量。
6. 因此不能把指标规格文件中的指标集合直接描述成实际 live 策略。；7. 必须把“规格存在”“模块可计算”“进入 live 决策”分成三种状态。；8. 在指标接线审计完成前，不应基于未接线指标做收益归因。；9. 不应把伪 CVD 的结果标记为真实主动买卖流。；10. 后续如引入真实 CVD，必须单独进行数据验证和对照实验。
### 2.5 第五问题：决策链存在多处替换和旁路
1. `total_score` 与四象限是两条独立计算路径。；2. `q1_green_channel` 可以替换主 decision，并进入 MAIN paper ledger。；3. 多周期 pending 路径、实验熔断、象限实验规则、声明式 gate 和 cap decision 在主循环中依次执行。；4. 一些 shadow 模块只记录，不拦截。；5. 一些风险模型只写快照，不参与下单阻断。
6. `entry_gates` 当前为空规则，不能把其存在描述成有效过滤器。；7. 五因子影子仅记录，不参与总分或交易动作。；8. 复杂链条中必须逐步记录每个决策改变前后的值。；9. 必须明确主 decision 的唯一 owner。；10. 不能继续通过叠加新 channel 或 shadow patch 解决已存在的决策解释问题。

---

## 3. 先建立唯一运行事实源
### 3.1 建立 Run Manifest
每次 dry-run、回测或 paper replay 都必须生成一份不可变 `run_manifest.json`。
至少记录：
- `run_id`；`started_at_utc`；`ended_at_utc`；`git_commit`
- `git_branch`；`working_tree_dirty`；`config_path`；`config_sha256`
- `resolved_config`；`cli_args`；`target_tier`；`post_close_delay_seconds`
- `kline_align`；`base_timeframe_seconds`；`universe_source`；`universe_version`
- `resolved_symbols`；`pnl_schema_version`；`pnl_accounting_mode`；`fee_bps`
- `slippage_bps`；`exit_mode`；`paper_or_backtest_mode`
### 3.2 运行配置冻结
1. 启动时读取配置后，生成 resolved config。；2. resolved config 应包含 dataclass 默认值和用户覆盖值。；3. 配置写入后不允许运行中静默改变。；4. 热更新仅允许监控级参数，不能更改交易参数。；5. 配置变更必须生成新 `run_id`。
6. 同一 `run_id` 禁止覆盖不同参数的输出。；7. 重启后必须生成新 run segment 并关联 parent run。；8. 所有服务启动参数必须从 manifest 复核。
### 3.3 配置源治理
1. 指定一个 canonical config 作为研究基线。；2. 指定一个 canonical config 作为 paper baseline。；3. 指定一个 canonical config 作为 staging baseline。；4. 不允许同时将 `regime_shadow`、`fib_pa_v1`、`v12`、`highest_win` 都描述为当前生产口径。；5. 变体配置必须写清 parent config 与差异字段。
6. 配置差异应由自动脚本生成，而不是人工维护表格。；7. dead config 键必须从配置删除，或标注 `deprecated` 并由 schema 拒绝使用。；8. 不允许死配置继续出现在示例文件中造成误导。；9. 配置读取失败必须 fail-fast，不允许静默回退到另一套策略。；10. 运行前对未知键、未读取键和互斥开关做验证。
### 3.4 Universe 快照治理
1. 动态 market-cap rank 只负责候选发现。；2. 最终可交易池必须落盘成确定性快照。；3. 快照必须包含 symbol、rank、来源、active 状态、生效时间和排除原因。；4. CLI `--symbols` 若覆盖 config，必须在 manifest 明确标记。；5. 回测必须使用历史时点 Universe，避免幸存者偏差。
6. paper 与 offline backtest 必须使用同一份 symbol snapshot 才能做公平比较。；7. symbol snapshot 不可被每日 summary 覆盖。；8. 添加或移除 symbol 都必须产生变更事件。；9. 已有持仓的 symbol 移出 Universe 后只能禁止新开仓，不应丢失持仓管理能力。；10. 不允许把“14 个币”误认为“同一批 14 个币”。

---

## 4. 统一当前实际生效的指标链
### 4.1 指标状态矩阵
建议为每个指标维护以下状态：
- `SPEC_ONLY`；`IMPLEMENTED`；`COMPUTED`；`LOGGED_ONLY`
- `LIVE_FEATURE`；`RISK_INPUT`；`DISABLED`
### 4.2 当前材料支持的事实
1. EMA 9/21/50/200 已参与当前特征链。；2. EMA200 当前配置为 soft penalty，而不是硬 veto。；3. EMA200 soft penalty 为 `-0.20` 的特征修正。；4. CCI live 评分使用 `cci_momentum_quality`，不是简单使用原始 CCI 单值。；5. CCI 质量按离散档位输出：14、10、7、3、0。
6. CCI 数据来自 15m high/low/close，period 20，观察近 5 根变化。；7. 当前 live `cvd_flow` 使用最近 6 根 candle 的涨跌方向乘成交量求和。；8. 真 CVD 的数据来源是 taker buy volume 与 total volume 的差额。；9. 真 CVD 和 live pseudo-CVD 不应在报告里混为一个指标。；10. Fibonacci location、price action structure 和 RR geometry 是当前 fib_pa score 的核心组成。
11. ATR / atr_pct 用于 volatility_stop、RR geometry 和 stop_pct 构造。；12. `volatility_stop` 在 `0.5% <= atr_pct <= 4%` 时给 1.0，否则给 0.2。；13. 该分档并不代表已充分验证波动率区间的预测能力。；14. RSI14 代码存在，但当前没有接入 `compute_indicator_results` 的 live 评分链。；15. BOLL 在提供的 live feature 总表中没有明确的有效读取路径。
16. MACD 在提供的 live feature 总表中没有明确的有效读取路径。；17. 五正交影子 F1-F5 仅写入日志/meta，不参与主决策。；18. 不能因五因子有分数输出，就认定它已经改变交易动作。；19. 规格层的指标责任定义必须与实际接线状态分开管理。；20. 所有 active feature 都必须有统一数据源、周期、计算窗口和质量标记。
### 4.3 建议的指标接线审计
1. 为每个指标提供唯一计算入口。；2. 为每个周期提供唯一缓存键。；3. 明确实时决策实际读到的字段名。；4. 在决策 payload 中记录 feature version。；5. 对缺失、过期、未完成 K 线输出 `quality_flag`。
6. 禁止各模块自行重算同一指标并使用不同窗口。；7. 对 pseudo-CVD 命名为 `candle_signed_volume_flow` 或等价名称。；8. 对真 CVD 命名为 `taker_flow_cvd` 或等价名称。；9. 不应将伪 CVD 直接替换成真 CVD 而不做对照实验。；10. 对 MACD/BOLL/RSI 的 live 状态给出明确结论：未接线、仅观测或已接线。
### 4.4 指标优化的优先次序
1. 先保证数据定义准确。；2. 再保证计算公式正确。；3. 再保证使用周期和窗口正确。；4. 再测试其增量预测价值。；5. 最后才决定是否给分或设为 hard gate。
6. 不应因为指标理论上经典就默认其适合当前策略。；7. 不应因为某指标在某个右尾交易上表现好就立即加大权重。；8. 不应重复加入高度相关的趋势特征。；9. 指标之间应有职责分工，而不是多指标投票堆叠。；10. 每增加一个 active feature，都必须说明它能否改善成本后净期望。

---

## 5. 评分架构与因子权重
### 5.1 当前运行架构的判定
1. `dynamic_weights` 先检查 `use_fib_pa_architecture`。；2. 若该开关为 true，会优先返回 `FIB_PA_WEIGHTS`。；3. 之后才检查 `use_ema_architecture`。；4. 当前 regime_shadow 配置两个开关都为 true。；5. 因此当前选择路径是 fib_pa，而不是 EMA 权重表。
6. EMA 权重表虽然存在，但当前配置下不是最终分支。；7. BASE / volatility dynamic weights 路径也不是当前实际命中路径。；8. 这类短路选择应在启动时打印一次并纳入 manifest。；9. 两个架构开关不应长期允许同时为 true。；10. 配置 schema 应将架构模式改为单选枚举。
### 5.2 当前 fib_pa 权重事实

| 分量 | 权重 |
|---|---:|
| `trend_ema_context` | 20 |
| `flow_cvd_confirmation` | 18 |
| `cci_momentum_quality` | 14 |
| `price_action_structure` | 22 |
| `fibonacci_location` | 18 |
| `risk_reward_geometry` | 8 |
| **合计** | **100** |
### 5.3 建议修复评分与象限不一致风险
1. `total_score` 当前由权重分量加总计算。；2. `quadrant` 当前按独立的轴条件计算。；3. 两者不是同一公式的不同展示。；4. 因此出现高分但低象限、低分但高象限并非逻辑上不可能。；5. 每次 decision 必须保存 `score_components`、`component_points`、`quadrant_axes` 和 `quadrant`。
6. 应建立 invariant tests，验证同一输入得到稳定的 score 与 quadrant。；7. 应增加 score-quadrant mismatch 统计。；8. 不建议立即强制让 quadrant 完全等于 score 分类。；9. 应先明确 quadrant 用于环境分类还是动作门槛。；10. 若两者职责不同，必须在文档中明确其不同用途。
### 5.4 阈值应采用明确配置档案
当前 regime_shadow 有效阈值推导为：
- LONG DIRECT：92。；LONG PROBE：77。；LONG WATCH：72。；SHORT DIRECT：82。
- SHORT PROBE：70。；SHORT WATCH：62。
建议：
1. 将有效阈值在 resolved config 中直接展开。；2. 不让调用方自行叠加偏移。；3. 明确 PROBE 的 long offset 是替换还是叠加。；4. 以最终值作为唯一运行口径。；5. 每次信号记录 threshold_profile_id。
6. 参数对比只改变一个 threshold family。；7. 记录各阈值的触发次数、转化率和后续收益。；8. 不只统计通过率，还统计被挡机会的后续 MFE/MAE。；9. 过高阈值可能减少样本，不必然改善净期望。；10. 阈值选择应以样本外净期望、回撤和成本后 PF 为依据。
### 5.5 避免评分系统继续膨胀
1. 暂停增加新的 score component。；2. 暂停增加新的 offset 层。；3. 暂停增加 score-specific promotion。；4. 对现有六个 fib_pa 分量做 ablation。；5. 每次 ablation 保持 Universe、费用、出场和撮合固定。
6. 不应只比较总分与胜率。；7. 应比较净期望、PF、成本率、样本数和集中度。；8. 删除无法产生增量价值且没有风险职责的分量。；9. 影子分量只有经过独立验证才可提升为 active。；10. 权重总和归一化不能替代特征有效性验证。

---

## 6. 多周期、象限与入场触发
### 6.1 当前多周期输入
1. 系统拉取 15m、30m、1h、4h K 线。；2. 15m 为基础决策周期。；3. 4h、1h、30m 的一致性分量使用 close 变化窗口。；4. lookback 分别为 4h=3、1h=4、30m=6。；5. 1h 方向函数观察最近若干根 close 的变化。
6. 若 1h 输出 NONE，当前代码还有 15m 最近几根方向回退。；7. 该 fallback 需要被明确记录，不能伪装成 1h 确认。；8. 15m 的极值位置比用最近 8 根 high/low/close 计算。；9. 多周期指标必须只使用已经收盘的 bar。；10. 4h 不应因为一根未收盘 bar 改变当前决策。
### 6.2 建议重新定义周期职责
- 4H：背景参考，不做频繁 veto。；1H：方向确认主层。；30m：趋势质量与延续确认。；15m：触发时机。
### 6.3 建议对方向与触发拆开记录
1. `direction_state` 只表达方向。；2. `trend_quality_state` 只表达趋势质量。；3. `trigger_state` 只表达入场时机。；4. `flow_state` 只表达资金流支持。；5. `risk_state` 只表达是否允许承担风险。
6. `entry_mode` 只表达执行级别。；7. 不使用一个 score 同时承载所有语义。；8. 每个输出都记录 timeframe 和 as-of timestamp。；9. 高周期数据不允许用未来 close 填充历史时间点。；10. 对齐错误应返回 `DATA_INVALID`，而不是默认中性。
### 6.4 4H 与 1H 背景冲突
1. 当前 4H 背景权重在 fib_pa 路径中并非独立分量。；2. 不应默认 4H 是强 veto。；3. 4H 反向但 1H/30m/15m 形成强确认时，可进入单独的研究分组。；4. 先记录反向背景样本，不要立即允许 full-size。；5. 4H NEUTRAL 应与 4H BEAR/BULL 分开统计。
6. 背景冲突规则必须进行分组回测。；7. 不应在同一实验中同时改变 4H 权重与 15m 触发阈值。；8. 4H 的主要价值应以收益分布和回撤差异证明。；9. 如果 4H 对 15m 机会造成明显延迟，应考虑只做风险降级。；10. 4H 参考定位与用户提出的低周期敏捷性要求一致，但仍需数据验证。

---

## 7. 通道和决策替换机制
### 7.1 当前关键事实
1. `q1_green_channel` 会调用 `_q1_trend_launch_eligible`。；2. 通过后会构造 `action=PROBE`、`leverage=1` 的决策。；3. 它会设置 `exit_mode=trend_capture` 与 `entry_channel=q1_trend_launch`。；4. 在主循环中该 channel 会替换主 decision。；5. 被替换后的决策进入 MAIN paper ledger。
6. 本窗口 `q1_trend_launch` 6 笔聚合净额为 `-0.179570`。；7. 该结果是小样本线索，且被单笔 BCH 损失影响。；8. 不能据此认定 q1 channel 永久无效。；9. 也不能把该通道当作已经验证的独立策略。；10. 当前行为必须被明确列入主策略，而不是作为“只是影子”的模块描述。
### 7.2 建议取消隐式 decision replacement
1. 主信号引擎应先产生 `primary_decision`。；2. Q1 channel 应产生 `channel_candidate`。；3. 两者应分别记录，不应无痕覆盖。；4. 若需要真正交易替换，应显式生成 `selected_decision`。；5. 记录 `decision_origin`。
6. 记录 `replaced_decision_id`。；7. 记录被替换前后的 action、score、side、leverage 和 exit_mode。；8. 回测必须重放完全相同的选择规则。；9. 独立研究通道最好使用独立 ledger。；10. 若要进入 MAIN，必须通过预先声明的 promotion gate。
### 7.3 通道实验验收
- 同一批原始候选机会。；同一套手续费与滑点。；同一止损与止盈模型。；同一 Universe snapshot。
- 同一 position sizing 规则。；唯一变化是通道选择策略。；比较净期望与风险，不只比较收益总额。；报告未通过、通过、执行、成交和出场各阶段数量。
- 若样本不足，结论必须为 INCONCLUSIVE。；不得将 shadow-only 账本视为真实风险暴露。
### 7.4 Q2/Q3 pending 与 Q1 转换
1. 当前 Q2/Q3 pending 路径有独立确认 bar 机制。；2. 应记录 candidate 创建、确认、过期和升级事件。；3. pending 状态不等于交易。；4. 观察候选不能被计入成交交易数。；5. Q2→Q1 与 Q3→Q1 必须分开统计。
6. 记录等待期间 MFE/MAE。；7. 记录确认所花 bar 数。；8. 记录确认后首次入场与候选价格的距离。；9. 评估确认延迟是否吞掉了主要趋势段。；10. 不要将 pending 数量当作策略交易能力。

---

## 8. 风控、仓位和杠杆
### 8.1 当前仓位逻辑的主要事实
1. `raw_notional = equity × risk_pct / stop_pct`。；2. DIRECT 和 PROBE 使用不同 risk_pct。；3. 当前配置的 direct risk_pct 为 `0.006`。；4. 当前配置的 probe risk_pct 为 `0.0015`。；5. leveraged cap 按 `equity × max_single_trade_risk_pct / (stop_pct × leverage)` 计算。
6. remaining exposure cap 由单币剩余暴露决定。；7. 最终名义为多个 cap 的最小值。；8. `binding_cap` 记录哪个约束最终限制名义。；9. `risk_first_sizing_enabled` 默认 false，当前四套配置均未显式启用。；10. 专门的 `position_sizer.py` 在评审材料中被标记为 spec-only，而非当前 live 主路径。
### 8.2 仓位优化建议
1. 将仓位计算唯一化，避免 signal、risk、execution 三处各算一遍。；2. 每次 sizing 必须记录完整中间值。；3. 记录 raw_notional。；4. 记录 leveraged_cap_notional。；5. 记录 remaining_exposure_notional。
6. 记录最终 binding_cap。；7. 记录 final_notional 与 final_qty。；8. 记录 quantity rounding 前后差值。；9. 记录 min notional 校验结果。；10. 如果 sizing 模块无法通过统一接口复现，不允许进入实盘链路。
### 8.3 leverage 建议
1. 当前杠杆选择包含 rolling Sharpe、ATR、score 和 fib_pa 条件。；2. leverage 不应被用来弥补信号不足。；3. 负 rolling Sharpe 触发降杠杆是风险保护，不应绕过。；4. 高 ATR 对杠杆的限制必须在报告中有单独统计。；5. 5x 应保持为严格受限的研究选项。
6. 任何 5x 交易都要记录触发条件和风险预算。；7. 同时报告 notional exposure 与 margin usage。；8. 不能把杠杆乘数后的 margin PnL 当策略 alpha。；9. 杠杆对总收益的影响必须与对回撤、爆仓距离和成本的影响并列报告。；10. 在止损前早期失败未解决前，不建议提升杠杆上限。
### 8.4 风险-first sizing
1. 评估 `risk_first_sizing_enabled` 是否应该成为唯一 sizing 路径。；2. 先建立等价性测试，保证开启前后风险公式含义清楚。；3. 比较风险预算、暴露 cap 和可用保证金谁是 binding constraint。；4. 对每次被 cap 截断的交易记录原因。；5. 不应通过 floor 将不可执行小仓抬大。
6. 不应在 execution adapter 中再次重算名义。；7. 对 Probe 与 Direct 分别计算实际风险，而不只看名义仓位比例。；8. 组合暴露应按相关组聚合，而不是只按 symbol 分散。；9. 同方向暴露和总暴露都需要监控。；10. 风控快照必须与下单指令使用同一时点数据。
### 8.5 Observation-only 风险模型
1. `net_beta_exposure_model` 当前为 observation-only。；2. `stress_decision` 当前只记录，不拦截。；3. 不能把这些输出当作已生效的硬风控。；4. 应保留其 shadow 输出用于评估。；5. 在决定接入 hard cap 前，先验证 false-positive 与 false-negative。
6. Shadow 模式与 enforcement 模式必须使用不同命名。；7. 接入硬风控必须增加 `RISK_BLOCKED` 事件。；8. 需要在回测中验证组合强制降仓行为。；9. 需要模拟风控服务不可用时的 fail-safe 行为。；10. 不允许以日志字段存在作为风控已完成的证据。

---

## 9. 出场逻辑优化
### 9.1 当前主账本 exit 顺序
主账本 `_update_position` 的关键逻辑是：
1. 幂等检查与 MFE/最佳价格更新。；2. early breakeven 检查。；3. post-TP stop 更新。；4. stop hit 命中时全平。；5. 否则进入 Q2 tightening。
6. 再检查 Q4 defensive exit。；7. 再检查 Q3 defensive reduce。；8. 再检查 TP1/TP2/TP3。；9. 检查 cost breakeven timeout。；10. 最后检查 max hold。
### 9.2 需要重点复核的退出细节
1. 同根 K 线 stop hit 优先于 TP hit。；2. 该顺序偏保守，但仍是一个撮合假设。；3. 若同根 K 线同时触及止损和止盈，必须记录 ambiguous_intrabar 状态。；4. 若没有更细粒度成交数据，采用 stop-first 是合理的保守基准。；5. 不允许在不同实验里悄悄改变 intrabar priority。
6. early breakeven trigger 与 post-TP stop 要明确是否可能同时修改 stop。；7. 一个 position 同一时刻只能有一个有效 stop price。；8. stop 更新必须 tighten-only，除非有明确的受控例外。；9. 止损修改都要留下 old_stop、新 stop、trigger reason。；10. 退出原因应区分策略退出、风险退出、时间退出和交易所保护退出。
### 9.3 当前参数一致性问题
- 主账本 TP levels 为 `1.2R / 2R / 3R`。；离线 lifecycle simulator TP levels 为 `1R / 2R / 3R`。；主账本 max hold 为 32 bars。；离线 lifecycle simulator max hold 为 16 bars。
- 主账本 legacy 与 trend_capture 的 trailing 规则不同。；主账本 paper exit mode 当前配置为 legacy。；scout_micro 配置可采用 trend_capture。
### 9.4 出场优化建议
1. 先统一 paper 与 backtest 的默认参数。；2. 不应让 1R TP 与 1.2R TP 同时代表同一套策略。；3. `max_hold_bars` 必须配置化并写入 run manifest。；4. `exit_mode` 必须进入每笔交易记录。；5. 在同一入场集上比较 legacy 与 trend_capture。
6. 排除单笔右尾的敏感性分析必须纳入出场比较。；7. TP fractions 应在每次 partial fill 中独立记账。；8. 开仓、部分退出、最终退出的手续费和滑点应逐项核算。；9. 记录持仓期间 MFE、MAE、bar offset 和所有 stop changes。；10. 不要只用最终 PnL 来判断出场机制优劣。
### 9.5 Cost breakeven timeout
1. 当前 timeout 条件与往返成本估算相关。；2. 该规则可能在价格未形成趋势时提前释放资金。；3. 需要统计 timeout 交易的后续反事实 MFE/MAE。；4. 记录 timeout 触发时的持仓 bars。；5. 记录 timeout 前是否曾达到 0.5R、1R 或其他有意义的盈利区间。
6. 对 timeout 退出进行 8/16/32 bar 对照。；7. 不应仅因 timeout 交易为负就删除它。；8. 不应仅因 timeout 交易为正就提高持仓上限。；9. 应测试 timeout threshold 的经济含义是否与 fee/slippage 模型一致。；10. 如果 timeout 主要切掉后来会恢复的仓位，才有证据考虑放宽。

---

## 10. 成本与交易经济学
### 10.1 当前成本事实
1. 事件流的 fee 合计约 `7.333288 USDT`。；2. 事件流的 slippage 合计约 `7.333288 USDT`。；3. 两者总计约 `14.666576 USDT`。；4. 入场成本摊分约 `7.342826 USDT`。；5. 出场成本约 `7.323750 USDT`。
6. 成本约占净额 `43.44%`。；7. 成本约占 gross PnL `30.28%`。；8. 该比例对小额交易影响明显。；9. 所有费用需按成交 notional 计算，不得重复对原始全仓收费。；10. 所有 slippage 需区分 entry 与 exit。
### 10.2 成本优化方向
1. 不要先降低假设费用以美化曲线。；2. 先验证 5 bps fee 和 5 bps slippage 是否与真实账户费率等级相符。；3. 若实际费率等级未知，使用保守值。；4. 记录 maker/taker 假设。；5. 市价单与限价单应采用不同成交成本模型。
6. 止损单、止盈单、breakeven stop 的滑点应允许分别估计。；7. 对每个 symbol 计算成本 / gross PnL。；8. 对每个 side 计算成本 / gross PnL。；9. 对每种 exit reason 计算成本 / gross PnL。；10. 成本过高时先研究减少低质量交易，而不是只追求更低费率。
### 10.3 交易频率的经济约束
1. 交易次数多不代表 edge 大。；2. 如果每笔毛收益很小，手续费和滑点会吞噬收益。；3. 如果交易次数减少但单笔净期望改善，策略可能更健康。；4. 每次实验必须报告平均 gross PnL、平均 cost 和平均 net PnL。；5. 需要报告扣除成本前后胜率是否改变。
6. 需要报告 break-even win rate。；7. 需要报告实际 payoff ratio。；8. 不应只用 win rate 作为优化方向。；9. 对低流动性标的，应增加更保守滑点压力。；10. 用成本压力测试确认 edge 的安全边际。

---

## 11. MAIN、SCOUT 与 A/B 实验账本治理
### 11.1 账本独立性
1. MAIN、scout_micro、AB legacy、AB trend_capture 是独立模拟账本。；2. 它们各自拥有独立的初始权益设定。；3. 不能把四套账本的 realized PnL 相加后称作组合收益。；4. 每份报告必须说明每个账本的用途。；5. Shadow-only ledger 不计入真实组合暴露。
6. Shadow-only 成交只能作为假设样本。；7. 主账本和实验账本必须使用不同的 `ledger_id`。；8. 交易事件必须包含 `experiment_id`。；9. 报表应将 actual/paper/shadow 明确区分。；10. 不允许同一 position 同时进入多个统计口径而不标注。
### 11.2 A/B 出场机制证据
1. AB 配对有 73 组匹配样本。；2. 其中 63 组两臂结果完全相同。；3. 6 组 legacy 更好，4 组 trend_capture 更好。；4. 一个 NEAR 配对贡献了绝大部分绝对差异。；5. 因此当前 A/B 差异并不能支持确定的出场机制优劣结论。
6. 必须报告 paired trade differences。；7. 必须报告排除最大差异交易后的结果。；8. 必须报告 bootstrap confidence interval。；9. 必须确保两臂入场集完全一致。；10. 若入场集不同，应先做匹配或重新运行同一入口集。
### 11.3 实验升级门槛
- 实验目的预先登记。；唯一主要变量预先登记。；失败条件预先登记。；样本门槛预先登记。
- 对照组保持不变。；运行配置和数据版本固定。；结果必须包含完整成本。；结果必须包含异常与缺失样本。
- 不能因一两笔交易改变主策略。；通过后先进入更长 paper 验证，不直接上真实交易。

---

## 12. 下一轮最重要的研究实验
### 12.1 实验 E0：重建运行事实
**目的：** 确认本窗口究竟运行了什么。  
**冻结：** 策略逻辑与参数不变。  
**动作：**
1. 从启动日志抽取真实配置路径。；2. 从磁盘读取当时配置内容或版本副本。；3. 确认 git commit 与未提交变更。；4. 解析最终 symbols 列表。；5. 复算 run manifest。
6. 检查日志轮转和 UTC 时间边界。；7. 对账全部 `paper_trades.jsonl`。；8. 按 `position_id` 重算 PnL。；9. 确认每个 ledger 的独立初始权益。；10. 通过后冻结新的研究基线。
**验收：** 所有数值可以独立复现；每个结论能定位到日志、配置或源码。
### 12.2 实验 E1：最大赢家集中度压力测试
**目的：** 判断正收益是否依赖单笔右尾。  
**保持不变：** 策略、费用、滑点、出场和 Universe。  
**报告：**
- 全样本 net PnL。；剔除最大赢家后的 net PnL。；剔除前两大赢家后的 net PnL。；Winsorized PnL sensitivity，仅作稳健性分析，不替代原始 PnL。
- HHI 与 top-1/top-2 profit concentration。；逐笔贡献排名。；每笔交易风险预算与实际收益 R。；右尾交易是否具有可重复的入场条件。
- 右尾交易在多个市场阶段是否复现。；右尾样本是否集中在单一 symbol 或单一日期。
**验收：** 不能只报告完整样本收益；必须同时报告剔除最大赢家后的敏感性。
### 12.3 实验 E2：单一架构基线
**目的：** 只保留一个明确评分架构。  
**方案：** 将架构选择改为互斥枚举，例如 `fib_pa`、`ema`、`base`。  
**步骤：**
1. 固定当前实跑 fib_pa 为 baseline。；2. 解析并打印实际权重表。；3. 禁止同时开启 fib_pa 与 EMA。；4. 在单独实验中比较 EMA 架构。；5. 每个架构使用同一数据集和同一 Universe。
6. 所有其他风险和执行参数固定。；7. 先比较信号集合差异。；8. 再比较风险通过和拒绝分布。；9. 最后比较成本后交易表现。；10. 结果不足时维持 baseline，不做主策略切换。
### 12.4 实验 E3：入场通道解耦
**目的：** 验证 Q1 trend launch 是否有独立增量价值。  
**实验组：** primary only、primary + channel shadow、channel-only replay。  
**要求：**
1. 原始 market context 完全一致。；2. primary decision 不被静默覆盖。；3. channel decision 独立输出。；4. 将两个决策分别保存。；5. 同一 position 不得双重计入 MAIN。
6. 对照同一批候选机会。；7. 比较触发、成交、出场、净 PnL 全链路。；8. 单独报告 6 笔 q1_trend_launch 的历史结果，不将其视为充分证据。；9. 对 BCH 负贡献做案例复盘，但不单独据此封禁。；10. 若增量价值不确定，保持 shadow-only。
### 12.5 实验 E4：出场机制配对
**目的：** 比较 legacy 与 trend_capture。  
**冻结：** 相同入场信号、价格、风险距离、数量、手续费、滑点。  
**只变：** post-TP stop mode。  
**输出：**
- 每笔配对净差。；平均配对差。；中位数配对差。；差异标准差。
- 最大绝对差交易占比。；排除最大差异交易后的配对差。；TP1/TP2/TP3 到达率。；MFE/MAE。
- stop move count。；holding time。
**验收：** 样本量与独立性不足时只能结论为 INCONCLUSIVE。
### 12.6 实验 E5：多空分组归因
**目的：** 判断多空两侧是否需要不同参数档案。  
**现状：** 主账本 7 笔 SHORT、4 笔 LONG，样本不足以做稳定阈值优化。  
**建议：**
1. 先累积更多 paper 样本。；2. 分别记录 long/short 的入场分数分布。；3. 分别记录 CVD flow 状态。；4. 分别记录 stop hit rate。；5. 分别记录 MFE/MAE。
6. 分别记录 cost / gross。；7. 分别记录 payoff ratio。；8. 分别记录按 symbol 聚合的交易结果。；9. 只在多个 rolling windows 中重复出现方向差异后，才引入独立阈值。；10. 不要因 4 笔多头交易就永久提高 long threshold。
### 12.7 实验 E6：成本敏感性
**目的：** 确定策略有多少安全边际。  
**实验组：** base cost、slippage +25%、slippage +50%、fee +25%、combined stress。  
**输出：**
- net PnL。；PF。；expectancy。；cost/gross。
- fee share。；entry slippage share。；exit slippage share。；break-even fee/slippage level。
- 不同 symbol 的成本敏感度。；不同 exit reason 的成本敏感度。
### 12.8 实验 E7：滚动窗口与块 bootstrap
**目的：** 验证是否存在稳定的样本外优势。  
**窗口：** 建议覆盖至少 6-12 个月可用数据。  
**要求：**
1. 使用滚动 30D 窗口。；2. 报告每个窗口的交易数。；3. 报告每个窗口的净收益和回撤。；4. 报告窗口中位数与 IQR。；5. 报告最差窗口。
6. 报告最好窗口，但不以其代表全局。；7. 按 symbol 和 side 分组。；8. 使用 block bootstrap 处理时间相关性。；9. 对不同 block length 做敏感性分析。；10. 不足样本的窗口标记 INCONCLUSIVE。

---

## 13. 具体策略优化建议
### 13.1 优先降低无效入场，而不是扩大交易次数
1. 当前 `q1_trend_launch` 6 笔净额略负，但样本太少。；2. 应进一步检查每次入场的 1H、30m、15m 状态。；3. 重点分析入场后 1-6 根 15m bar 的反向波动。；4. 若许多失败单在 1-3 根 bar 内止损，优先研究触发时机。；5. 若失败单在多个 bar 后才止损，重点研究趋势失效识别。
6. 不应直接扩大 stop distance。；7. 扩大止损时必须按相同风险预算同步缩小名义。；8. 不能通过降低费用假设提升小幅交易的盈利率。；9. 不能把 WATCH 转换成 PROBE 来制造更多交易。；10. 先提高每笔候选的净质量，再考虑增加频率。
### 13.2 研究 CCI 动量分档
1. 当前 live CCI quality 使用 14/10/7/3/0 离散分档。；2. 需要统计每个档位的实际样本数。；3. 统计每个档位的入场后 MFE/MAE。；4. 统计每个档位的 stop hit rate。；5. 统计每个档位的 net expectancy。
6. 对各档位做成本后比较。；7. 如果某档位只在单一 symbol 有效，不应全局提升权重。；8. 不应只凭 CCI 极值推断趋势强度。；9. 对多空分开评估 CCI 质量分布。；10. 未经滚动验证，不改变当前档位阈值。
### 13.3 研究伪 CVD 与真 CVD 的差异
1. 当前 live flow 不是逐笔主动买卖 CVD。；2. 其计算依据是最近 6 根 K 线 close/open 方向乘 volume。；3. 真 CVD 依赖 taker buy volume 与 total volume。；4. 两种数据的语义不同。；5. 对同一时间点并行计算两者。
6. 不要先替换 active feature。；7. 对比信号一致率。；8. 对比方向分歧时的后续收益。；9. 对比两者对假突破和早期止损的识别能力。；10. 真 CVD 缺失时应标记 unavailable，不要伪造为 0。
### 13.4 研究 EMA200 soft penalty
1. 当前 EMA200 是 soft penalty 模式。；2. 不应未经验证切回 hard veto。；3. 对比不使用 EMA200、soft penalty、hard gate 三种研究组。；4. 固定其余评分和风险设置。；5. 分方向报告。
6. 分 4H 背景状态报告。；7. 记录被阻止的机会后续表现。；8. 记录软惩罚降低分数后 action 改变的案例。；9. 统计 EMA200 距离与结果的分桶。；10. 只在样本外稳定后决定是否保留。
### 13.5 研究 Fibonacci 与 Price Action
1. Fibonacci location 在 fib_pa 总分中占 18 权重。；2. Price action structure 占 22 权重。；3. 两者合计占 40 分。；4. 该权重较高，应重点验证增量贡献。；5. 做 fib-only、PA-only、fib+PA、neither 的 ablation。
6. 所有组使用同一入场和退出模型。；7. 对 fractal swing 的时间确认做 look-ahead 检查。；8. 对 Fibonacci tolerance 与 ATR 关系做敏感性分析。；9. 删除未被读取的 fib swing 配置键或接通并测试。；10. 不允许配置显示 lookback 30，而函数实际使用 50 的漂移继续存在。
### 13.6 研究 RR geometry
1. 当前 RR geometry 使用 ATR 生成 stop distance。；2. stop distance 被 clamp 在价格的 0.5%-3% 区间。；3. TP1 在该评分中按 1.2 倍 stop distance 估算。；4. 当前 `min_rr_net_r` 某些路径可能因 `rr_detail=None` 而不生效。；5. 需要确认每个 RR 配置是否真正进入决策。
6. 记录理论 RR 与真实成交 RR 的差值。；7. 记录 opposition swing distance。；8. 记录 TP1 目标扣除费用后的净 R。；9. 对止损距离过大和过小的样本分组。；10. RR 分数不能替代真实执行成本模型。
### 13.7 研究流动性 gate
1. 当前 liquidity ratio 根据 24h quote volume、ATR 百分比和 expected order size 计算。；2. ratio 小于 8 时 NO_TRADE。；3. ratio 小于 20 时 DIRECT 可降级为 PROBE。；4. 必须确认 expected_order_size 与最终名义仓位是否一致。；5. 若 expected_order_size 是固定预估值，应与实际 final_notional 做比较。
6. 不应把历史成交额直接等同于盘口可成交深度。；7. 后续可加 spread 和 order-book depth 作为执行约束，但不能未经实测进入评分。；8. 报告每个 symbol 的 liquidity ratio 分布。；9. 报告 gate 阻断后市场实际走势作为 counterfactual。；10. 只有确认 gate 能减少成本或尾部风险后才保留。

---

## 14. 对目标收益与胜率的处理
### 14.1 不应直接把 50% 回报和 80% 胜率当成调参方向
1. 目标值是经营目标，不是统计证据。；2. 高胜率不必然代表高期望值。；3. 低胜率也可能在高 payoff 下产生正期望。；4. 当前样本的高 PF 受单笔右尾影响，不能作为高质量证据。；5. 不应为了提高胜率而砍掉大赢家。
6. 不应为了追求 50% 月收益提高杠杆。；7. 先定义可接受最大回撤。；8. 再定义可承受的成本率和单笔风险。；9. 再评估净期望与收益分布是否有改善。；10. 只有多个滚动窗口支持后，才讨论是否接近目标。
### 14.2 目标评估必须增加的指标
- 中位数 rolling 30D return。；最差 rolling 30D return。；90th percentile 与 10th percentile return。；最大回撤与回撤持续时间。
- 每月 trade count。；成本 / gross。；最大赢家占总盈利比例。；前两大赢家占总盈利比例。
- 去除最大赢家后的回报。；净收益在 symbol、side 和 exit reason 上的集中度。
### 14.3 风险约束优先
1. 先用当前名义杠杆和风险预算验证信号质量。；2. 不允许把目标回报差距转化为自动加杠杆理由。；3. 不能以低样本最大回撤很低就推断尾部风险很低。；4. 不能用纸面模拟成交速度推断实盘成交质量。；5. 保证金占用与名义暴露应分开报告。
6. 风险预算应基于 stop distance，而不是固定金额印象。；7. 组合风险必须包括相关资产的共同方向暴露。；8. 日亏损、周亏损、总回撤阈值应独立测试。；9. 所有 hard cap 的触发都要有清晰的事件日志。；10. 风控不可用时默认禁止新开仓。

---

## 15. Codex 落地顺序
### Task 0：先审计，不改策略
- [ ] 读取当前分支和 git status。
- [ ] 读取真实运行配置与服务启动命令。
- [ ] 生成 resolved config。
- [ ] 生成 symbol universe snapshot。
- [ ] 校验 PnL schema。
- [ ] 对账 MAIN ledger。
- [ ] 对账所有独立 shadow ledger。
- [ ] 输出 active/dead/shadow feature matrix。
- [ ] 输出 scoring architecture resolution。
- [ ] 不触碰 Binance client。
### Task 1：运行事实源
- [ ] 新增 `run_manifest.json`。
- [ ] 增加 config checksum。
- [ ] 增加 resolved config dump。
- [ ] 增加 git commit 与 dirty flag。
- [ ] 增加 resolved symbols。
- [ ] 增加 pnl schema version。
- [ ] 增加 active score architecture。
- [ ] 增加 active exit mode。
- [ ] 增加 fee/slippage assumptions。
- [ ] 增加运行前 manifest validation。
### Task 2：指标接线治理
- [ ] 建立 feature registry。
- [ ] 给每个指标标记 SPEC_ONLY / LIVE_FEATURE / LOGGED_ONLY 等状态。
- [ ] 明确真实 CVD 与 pseudo-CVD 命名。
- [ ] 明确 RSI 是否参与计算与评分。
- [ ] 明确 MACD/BOLL 是否参与 live 决策。
- [ ] 对死配置增加测试。
- [ ] 对未读取配置发出启动 warning 或直接拒绝。
- [ ] 所有 active feature 写入决策证据。
- [ ] 加入数据质量标记。
- [ ] 增加 feature version。
### Task 3：评分架构唯一化
- [ ] 将两个架构 bool 改为单选 architecture enum。
- [ ] 保留现有 fib_pa 参数作为 baseline。
- [ ] 添加 resolved weights 输出。
- [ ] 增加 weights sum invariant。
- [ ] 增加 score 与 component points 对账测试。
- [ ] 增加 quadrant axes 独立计算测试。
- [ ] 统计 score/quadrant mismatch。
- [ ] 增加阈值最终值输出。
- [ ] 删除重复未调用的本地 helper。
- [ ] 不在本任务中更改权重数值。
### Task 4：决策替换治理
- [ ] 将 primary decision 与 channel candidate 分开。
- [ ] 增加 decision_origin。
- [ ] 增加 replaced_decision_id。
- [ ] 增加替换前后字段快照。
- [ ] Q1 channel shadow-only 对照输出。
- [ ] 明确是否进入 MAIN ledger。
- [ ] 不允许一个机会重复计为两笔 MAIN 交易。
- [ ] 为 Q2/Q3 pending 加候选生命周期统计。
- [ ] 对所有 gate 记录触发原因。
- [ ] 加入 decision trace replay 测试。
### Task 5：仓位和风险接口
- [ ] 统一 position sizing 接口。
- [ ] 暂时保持现有风险参数不变。
- [ ] 输出所有 sizing intermediate values。
- [ ] 输出 binding_cap。
- [ ] 输出 leverage selection reason。
- [ ] 校验 risk_first_sizing_enabled 当前路径。
- [ ] 确认 position_sizer.py 是否属于 live path。
- [ ] 移除执行层重复 sizing。
- [ ] 验证 min notional 不会抬高仓位。
- [ ] 为风险模块不可用增加 fail-safe。
### Task 6：退出参数同构
- [ ] 统一 TP1 的 `1.0R` 与 `1.2R` 差异。
- [ ] 统一 max hold `16` 与 `32` 差异。
- [ ] 明确默认 exit_mode。
- [ ] 为 partial exits 保存完整成交数据。
- [ ] 对入场和出场分别计算费用。
- [ ] 对入场和出场分别计算滑点。
- [ ] 记录 MFE/MAE。
- [ ] 记录 stop update history。
- [ ] 增加 intrabar ambiguity 标记。
- [ ] 确认 paper/backtest 使用同一退出实现或经过等价性测试。
### Task 7：研究回测
- [ ] 固定数据集和时间范围。
- [ ] 固定 Universe snapshot。
- [ ] 固定费用与滑点。
- [ ] 固定入场策略。
- [ ] 先跑当前 baseline。
- [ ] 再跑单变量 ablation。
- [ ] 做最大赢家敏感性。
- [ ] 做 side 分组。
- [ ] 做 symbol 分组。
- [ ] 做 rolling window 与 block bootstrap。
### Task 8：报告生成
- [ ] 输出每笔完整生命周期。
- [ ] 输出每个 ledger 独立统计。
- [ ] 输出 PnL reconciliation。
- [ ] 输出 cost breakdown。
- [ ] 输出最大赢家 concentration。
- [ ] 输出样本量与有效样本量。
- [ ] 输出配置漂移检查。
- [ ] 输出 active feature matrix。
- [ ] 输出 experiment grid。
- [ ] 输出研究结论与部署决定。

---

## 16. 测试与验收标准
### 16.1 数据与配置验收
- [ ] 同一 run_id 对应唯一 config hash。
- [ ] 同一 run_id 对应唯一 universe snapshot。
- [ ] 启动日志与 manifest config path 一致。
- [ ] 未知 config key 必须 fail-fast。
- [ ] dead config 不能被误标为 active。
- [ ] 运行时架构只能解析为一种。
- [ ] CLI override 必须可见。
- [ ] UTC 与本地时区转换测试通过。
- [ ] 所有指标只使用已收盘 K 线。
- [ ] 周期对齐测试通过。
### 16.2 PnL 与账本验收
- [ ] 每个 position 的 partial exits 之和不超过原始数量。
- [ ] 全部出场数量最终等于开仓数量。
- [ ] `net_pnl_full` 与 entry/exit cost 对账。
- [ ] summary realized PnL 与逐笔 position PnL 对账。
- [ ] 不跨日求和累计 summary counter。
- [ ] 不合并独立 ledger。
- [ ] deprecated margin PnL 不进入主要报告字段。
- [ ] 交易数量按 position_id，而不是出场事件行数。
- [ ] 同一订单重放不重复入账。
- [ ] 每个 PnL 字段定义有单元测试。
### 16.3 决策链验收
- [ ] primary decision 不会被隐式覆盖。
- [ ] channel replacement 必须显式记录。
- [ ] score 与 quadrant 都可复算。
- [ ] 所有 gate reason 可追踪。
- [ ] pending candidate 不计为真实成交。
- [ ] observation-only model 不会静默拦单。
- [ ] hard gate 的优先级固定。
- [ ] 数据质量失败能够阻断新开仓。
- [ ] 同样输入在回测和 paper 产生相同决策。
- [ ] 决策 trace 可完整回放。
### 16.4 风险与执行验收
- [ ] 仓位只计算一次。
- [ ] 最终名义不超过任何 binding cap。
- [ ] 杠杆决策有 reason code。
- [ ] 保证金与名义暴露区分。
- [ ] 保护单数量与真实持仓一致。
- [ ] 部分成交后保护单同步正确。
- [ ] 持仓不同步时禁止新开仓。
- [ ] 风控模块故障时进入安全模式。
- [ ] 重复订单请求具备幂等性。
- [ ] 真实 Binance client 不被研究代码擅自修改。
### 16.5 统计验收
- [ ] 所有报告同时显示名义样本和有效样本。
- [ ] 进行块长敏感性分析。
- [ ] 有 rolling window 结果。
- [ ] 有最大赢家剔除敏感性。
- [ ] 有 symbol/side 分组。
- [ ] 有成本压力测试。
- [ ] 有净期望和 payoff ratio。
- [ ] 有成本后 PF。
- [ ] 有最大回撤和回撤持续时间。
- [ ] 样本不足时输出 INCONCLUSIVE。

---

## 17. 部署决策门槛
### 17.1 当前结论
**当前材料不支持真实资金部署。**
原因：
1. 样本量不足。；2. 正收益高度依赖单笔 NEAR 交易。；3. 去除最大赢家后净收益很薄。；4. 胜率仅为 27.27%。；5. 成本占净收益比例较高。
6. 配置与运行文档存在漂移。；7. 指标规格与实际 live feature 链存在差异。；8. 出场参数在 paper 与 backtest 间不一致。；9. channel replacement 使主决策路径不够单一。；10. 块 bootstrap 与多块长敏感性尚未完成。
### 17.2 进入下一阶段前的最低条件
- 运行事实源完整。；配置和 Universe 可复现。；PnL 口径完全一致。；活跃指标接线表完整。
- 评分架构唯一。；决策替换路径可审计。；主账本与回测退出参数一致。；至少覆盖 6 个月的滚动研究数据。
- 正期望不依赖单笔最大赢家。；保守成本压力下仍存在统计上可解释的优势。
### 17.3 纸面运行要求
1. 完成离线验证后继续 paper。；2. paper 期间禁止策略参数无记录热改。；3. 每次版本升级都保留前后版本对照。；4. 记录每个信号从候选到成交的完整漏斗。；5. 记录执行延迟和模拟滑点。
6. 记录保护单与持仓同步状态。；7. 记录连续亏损和每日风险状态。；8. 纸面结果应覆盖不同市场阶段。；9. 不以单周盈利为上线理由。；10. 每次部署 review 都应有明确 PASS / FAIL / INCONCLUSIVE。

---

## 18. 推荐的最终系统结构
### 18.1 决策主线

```text
Market Data
  -> Data Quality
  -> Indicator Features
  -> Multi-Timeframe Context
  -> Primary Signal
  -> Explicit Channel Selection
  -> State Transition
  -> Risk Approval
  -> Position Sizing
  -> Execution Request
  -> Paper / Exchange Adapter
  -> Position Reconciliation
  -> Event Log / Database
  -> Reports
```
### 18.2 每层职责
- Data Quality：判断数据可用性和时间完整性。；Indicator Features：只计算特征，不决定交易。；Multi-Timeframe Context：整合周期状态，不下单。；Primary Signal：输出主信号与证据。
- Channel Selection：只选择显式候选，不隐式覆盖。；State Transition：执行有限状态转换。；Risk Approval：允许、缩小、拒绝或要求退出。；Position Sizing：计算最终数量与 cap。
- Execution Request：表达订单意图。；Adapter：标准化交易所请求与响应。；Position Reconciliation：以交易所/账本事实核对持仓。；Event Log：保存可追溯事件。
- Reports：统计结果，不重新解释策略逻辑。
### 18.3 所有决策必须回答的问题
- 使用了哪个 config？；使用了哪个 Universe snapshot？；使用了哪些已完成 K 线？；使用了哪些 active features？
- 哪个 scoring architecture 生效？；为什么形成该 signal？；哪个 gate 通过或阻断？；哪个通道被选中？
- 为什么进入该 state？；风险预算是多少？；哪个 binding cap 限制仓位？；最终数量是多少？
- 订单是否成交？；实际成本是多少？；最终退出原因是什么？

---

## 19. 下一轮研究的优先级总表

| 优先级 | 工作 | 主要目的 | 是否改策略参数 |
|---|---|---|---|
| P0 | Run manifest 与配置冻结 | 可复现 | 否 |
| P0 | PnL/ledger 对账 | 数据可信 | 否 |
| P0 | Active/dead/shadow feature matrix | 真实机制清晰 | 否 |
| P0 | 单一评分架构 | 避免架构短路歧义 | 否 |
| P0 | primary/channel 决策解耦 | 消除隐式替换 | 暂不 |
| P0 | paper/backtest exit 同构 | 比较公平 | 统一参数 |
| P1 | 最大赢家敏感性 | 测量集中风险 | 否 |
| P1 | CVD 真/伪对照 | 测量订单流增量 | shadow first |
| P1 | CCI/Fib/PA ablation | 测量因子增量 | 单变量 |
| P1 | 成本敏感性 | 测量安全边际 | 成本模型 |
| P2 | Long/Short profile | 方向差异验证 | 研究中 |
| P2 | Legacy/Trend capture paired test | 出场效果比较 | 单变量 |
| P2 | Rolling windows/block bootstrap | 稳健性 | 否 |
| P3 | 风险硬约束与 staging | 部署准备 | 经验证后 |

---

## 20. 最终建议
1. 把当前 `+33.762404 USDT` 记为“单窗口 paper 主账本已核实净收益”，不要记为“策略已证明盈利”。；2. 把最大赢家贡献 `97.59%` 作为下一轮研究的首要风险提示。；3. 把 `n_eff=9` 和 bootstrap 未运行作为统计限制写进每份报告。；4. 先修复配置漂移和 Universe 复现，再讨论评分参数。；5. 先明确真正参与 live 决策的指标，再讨论新增 MACD、BOLL 或 RSI。
6. 将伪 CVD 与真 CVD 分开命名、分开测试。；7. 把 fib_pa / EMA / BASE 架构改为互斥配置。；8. 将 `q1_green_channel` 从隐式主决策替换改为显式通道选择。；9. 暂不增加杠杆，不以 50% 收益目标强制调整风险预算。；10. 不把 80% 胜率当成唯一优化目标，优先净期望、集中度、成本率和回撤。
11. 统一 paper 与 backtest 的 TP1、max hold 和 exit mode。；12. 用同一入场集比较不同出场机制，并剔除最大差异交易做敏感性分析。；13. 为每个 active feature 做增量价值测试，不能凭指标名称决定权重。；14. 对每个实验预先登记唯一变量、成功标准、失败标准和样本门槛。；15. 报告无法支持结论时，必须明确写 INCONCLUSIVE。
16. 研究阶段应优先消除“不可复现”和“无法归因”，而不是持续加策略功能。；17. Codex 应先完成 P0 工程治理，之后再实施 P1/P2 研究实验。；18. 所有研究变更都应与 `binance_client.py` 和真实下单路径隔离。；19. 在足够样本、跨窗口稳定性和保守成本验证之前，保持 paper-only。；20. 当前最有价值的优化不是让系统交易更多，而是让每一笔交易的来源、风险、成本和结果都能被准确解释。

---

## 附录 A：下一轮实验报告固定模板
每个实验必须至少包含以下字段：
- `experiment_id`；`hypothesis`；`parent_run_id`；`control_run_id`
- `changed_variables`；`frozen_variables`；`git_commit`；`config_hash`
- `universe_snapshot_id`；`data_version`；`start_time_utc`；`end_time_utc`
- `trade_count`；`effective_sample_size`；`win_rate`；`profit_factor`
- `expectancy`；`payoff_ratio`；`gross_pnl`；`entry_cost`
- `exit_cost`；`net_pnl_full`；`cost_to_gross_ratio`；`max_drawdown`
- `max_drawdown_duration`；`top1_profit_share`；`top2_profit_share`；`ex_top1_net_pnl`
- `ex_top2_net_pnl`；`long_metrics`；`short_metrics`；`symbol_metrics`
- `exit_reason_metrics`；`rolling_window_metrics`；`bootstrap_metrics`；`deployment_status`

## 附录 B：实验状态枚举
- `PASS`：预先定义的验收条件全部满足。；`FAIL`：至少一个硬性验收条件未满足。；`INCONCLUSIVE`：样本不足或统计区间不能支持结论。；`NOT_RUN`：尚未执行，不能当作通过。
- `BLOCKED`：因数据、配置或工程问题不能运行。

## 附录 C：必须长期保留的研究纪律
1. 保留原始交易事件，不只保留汇总结果。；2. 保留所有拒绝信号，不只保留成交信号。；3. 保留所有 gate 的命中原因。；4. 保留每次决策的指标快照。；5. 保留每笔仓位的 sizing 计算链。
6. 保留每次 stop price 变化。；7. 保留每笔 partial exit。；8. 保留所有费用和滑点明细。；9. 保留所有配置与 Universe 快照。；10. 保留失败实验，不得只归档成功版本。
11. 不得用新的 summary 覆盖旧的 summary。；12. 不得对历史交易数据进行无审计修改。；13. 不得将 shadow 假设成交混入主账本。；14. 不得把观察指标标记为已生效风控。；15. 不得把未运行测试标记为通过。
16. 不得在小样本上追逐高胜率。；17. 不得为了目标收益放宽风险约束。；18. 不得让 Codex 自行猜测未定义的业务语义。；19. 不得让回测与 paper 使用不同策略主链。；20. 不得在没有验收报告的情况下推进真实资金部署。
**文档结束。**
