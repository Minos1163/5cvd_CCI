# 部署

当前**唯一**生产单元：`deploy/systemd/ai300-dry-run.service`（Binance USDT 永续 15m 纸面交易）。

历史上仓库曾有三份互不一致的 unit（`ai300-dry-run.service`、`aibot.service`、
`ai300-shadow-regime.service`），2026-11-09 收敛为一份：`aibot.service` 与前者逐字重复且同样错误、
VPS 从未安装，`ai300-shadow-regime.service` 指向的工作目录已改名不存在、且 regime overlay
已由主实例的 `paper_ab` 三臂（legacy / pure_ladder / trend_capture）覆盖，两者均已删除。

## 安装

```bash
sudo cp deploy/systemd/ai300-dry-run.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai300-dry-run
```

或 `sudo bash scripts/vps_ops.sh install-unit`（同样需要 sudo）。

## 口径事实表

| 项 | 值 |
| --- | --- |
| 工作目录 | `/root/AIBOT` |
| 解释器 | `/root/anaconda3/bin/python`（无 venv） |
| config | `configs/entry_chain.dry_run_regime_shadow.json` |
| target tier | `conservative`（未传 `--target-tier`） |
| 收盘延迟 | `--post-close-delay-seconds 10` |
| 日志根 | `/root/AIBOT/logs` |

**以启动日志为唯一事实基线**：日志首行 `=== AI300_DRY_RUN cycle N @ ... ===` 与紧随的
`DRY-RUN安全: ... config=...` 行记录了实际口径，任何表格与它冲突时以日志为准。

## 运维

```bash
bash scripts/vps_ops.sh status    # 进程 / ExecMainPID 对照，可发现双实例
bash scripts/vps_ops.sh health    # 进程数、最新日志、cycle 计数与最近 3 条 tail
bash scripts/vps_ops.sh tail      # tail -f 最新 runtime 日志
```
