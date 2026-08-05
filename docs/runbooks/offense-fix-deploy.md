# 进攻修复部署指引(offense-fix-deploy runbook)

> 适用: 2026-08-04 Phase 0-3 修复集(q1_trend_launch 死规则修复 / LONG probe 校准 / SCOUT mission 校准 / Payoff 试点 / 追踪协议)。
> 目标环境: VPS(systemd 服务 `ai300-dry-run.service`, 日志根 `/root/AIBOT/logs`)。

## 1. 前置检查(本地)

```bash
# 1) 全量单测
python -m pytest tests/ -q

# 2) 配置卫生
python scripts/audit_duplicate_json_keys.py

# 3) 追踪协议状态(必须: 不得有未知 P0)
python scripts/recommendation_tracker.py check
```

## 2. 变更清单(2026-08-04)

| 文件 | 变更 |
|---|---|
| scripts/run_live_dry_run.py | `_q1_trend_launch_eligible` 删除确认标签依赖(L888), 加非极值追单检查; probe quadrant 配置化; trend_capture mirror 试点 |
| src/signals/entry_chain_features.py | 新增 `extreme_position_ratio` |
| src/signals/entry_chain.py | EntryChainContext 加 `extreme_position_ratio` |
| src/signals/entry_chain_config.py | 新增 trend_launch 极值字段 / probe quadrants / mirror payoff pilot 字段; watch_only_promotion_min_score 87→85 |
| src/observability/paper_trading.py | PaperExitConfig 加 early_breakeven; `_apply_early_breakeven` |
| configs/entry_chain.dry_run_fib_pa_v1.json | 上述配置值 |
| scripts/recommendation_tracker.py / audit_duplicate_json_keys.py / verify_q1_trend_launch_fix.py / diagnose_*.py / evaluate_offense_fixes.py | 新增工具 |
| docs/recommendations_tracking.md | 追踪表(14 条建议状态) |

## 3. VPS 部署步骤

```bash
# 3.1 同步代码到 VPS(按现有部署方式, 例如 rsync/git pull)
rsync -av --exclude logs --exclude data ./ user@vps:/root/AIBOT/

# 3.2 重启 dry-run 服务(加载新配置与新代码)
ssh user@vps "sudo systemctl restart ai300-dry-run.service"

# 3.3 确认进程健康
ssh user@vps "sudo systemctl status ai300-dry-run.service --no-pager"
```

## 4. 部署后立即验证

```bash
# 4.1 重启后 15 分钟内: 确认新配置被加载(summary.json 中 dry_run_assumptions 含新字段)
# 4.2 运行 24h 后:
cd /root/AIBOT && python scripts/verify_q1_trend_launch_fix.py --mode online --log-root logs --hours 24
#   预期: q1_trend_launch 相关决策数 > 0 且废弃标签残留 = 0(退出码 0)

# 4.3 运行综合评估(样本积累后, 建议每 2-3 天):
cd /root/AIBOT && python scripts/evaluate_offense_fixes.py --log-root logs --days 3
#   预期: q1_trend_launch 有转化; probe 平仓 20 笔后 PF>1; payoff A/B 30 笔后 trend 优于 legacy
```

## 5. 熔断与回滚

- q1_trend_launch 修复部署 48h 后仍 0 转化 → 人工介入代码审查(不得假设"配置写了就生效")
- probe 前 10 笔中连续 5 笔止损 → 关闭 probe(`scout_micro_high_score_long_offset_min_score` 恢复 85 或禁用)
- 任何验证脚本失败 → 视为修复未完成, 回滚对应变更:
  ```bash
  # 回滚示例: 恢复旧 run_live_dry_run.py 并重启
  ssh user@vps "sudo systemctl restart ai300-dry-run.service"
  ```

## 6. 观察窗口与验收(Phase 3-4)

| 项目 | 验收窗口 | 成功标准 |
|---|---|---|
| q1_trend_launch | 24-48h | ≥3 笔实验账本转化; 在线验证 PASS |
| LONG probe | 20 笔平仓 | PF>1 → offset 可按分布校准; PF<0.8 → 暂停 |
| Payoff A/B | 30 笔 | trend_capture PF > legacy 且 payoff 改善 |
| watch_only promotion | 1 周 | ≥1 笔触发(85 分门槛校准后) |

## 7. 下一份报告开篇(强制)

任何新诊断报告开篇必须包含"上轮建议实施回顾"表格(`docs/recommendations_tracking.md` 内容),
且先运行 `python scripts/recommendation_tracker.py check`——存在未解决 P0 时必须逐条说明阻塞原因, 不得直接分析新窗口数据。
