# AI300 P0 工程治理实施计划

> **给 Codex：** 按 Task 顺序逐条执行，不要跨任务合并提交。每个 Task 结束前必须跑该 Task「验收」里的命令，输出贴进 commit body。遇到与本文事实不符，**以源码为准并停下来记录**，不要自行改设计。
> 本计划由 writing-plans 生成，按 subagent-driven-development 执行：每个 Task 派独立实现者 → 规格复核 → 质量复核 → 才进下一个。
> **P0 全程不改任何策略参数。** 任何看起来像"顺手调一下"的改动都是越界。

**Goal:** 在不改变任何策略参数与交易行为的前提下，把"这次运行到底跑了什么、每笔交易为什么发生、盈亏是怎么算出来的"做成可复现、可对账、可审的工程事实。

**Architecture:** 四层加固，自下而上：(1) 运行事实层 —— 每次运行落盘不可变 `run_manifest.json`；(2) 语义层 —— 指标/分量接线矩阵与被证伪项集中登记；(3) 决策层 —— 架构单值解析 + 决策替换留痕；(4) 核算层 —— 仓位计算单次化轨迹 + 出场参数同构 + 账本对账回归测试。所有改动均为**加可观测性与加断言**，不触碰信号阈值、权重、杠杆、TP 与 universe。

**Tech Stack:** Python 3.13（venv `.venv/Scripts/python.exe`）、pytest、dataclasses、hashlib、subprocess(git)、pathlib。不引入新第三方依赖。

---

## 0. 前置事实（2026-11-09 11:20 实测，全部可复核）

| 项 | 实测值 | 复核方式 |
|---|---|---|
| git HEAD | `73388a5` | `git rev-parse --short HEAD` |
| 分支 | `20261031-v2` | `git branch --show-current` |
| 工作树 | **脏**：8 个已改 + 9 个未跟踪 | `git status --short` |
| pytest 基线 | `1 failed, 870 passed`（耗时约 50s） | 见 Task 0 命令 |
| 唯一失败用例 | `tests/test_describe_indicator_rules.py::test_describe_indicator_rules_outputs_completed_03_contract` | 同上 |
| `docs/plans/` | 本次新建 | — |
| live 主循环行数 | 3251 | `wc -l scripts/run_live_dry_run.py` |

已改文件：`CODEBUDDY.md`、`configs/entry_chain.dry_run_fib_pa_v1.json`、`scripts/run_live_dry_run.py`、`scripts/vps_dry_run_healthcheck.py`、`tests/test_dry_run_configs.py`、`tests/test_entry_chain_config.py`、`tests/test_live_dry_run.py`，以及已删除的 `configs/entry_chain.dry_run.json`。
未跟踪：`configs/entry_chain.dry_run - 副本.json`、`configs/trading_config_fund_flow.json`、`docs/2026-10-20-restructuring-plan-v2-review.md`、`docs/2026-10-31-paper-run-review-and-recommendations.md`、`docs/AI300_strategy_optimization_advice.md`、`docs/AI300_策略指标因子与决策逻辑_评审稿_20261108.md`、`docs/analysis/2026-10-31_to_11-08_loss_attribution.md`、`logs_parallel/`。

### 0.1 本计划对 V1.0 的六处修正（影响工时与改法，必须先读）

| 编号 | V1.0 的说法 | 实测事实 | 对 P0 的影响 |
|---|---|---|---|
| D1 | 「`q1_green_channel` **可以**替换主 decision」 | `run_live_dry_run.py:256-272` 每周期**无条件调用** `build_q1_green_channel_decision`，返回非 `None` 即覆盖 `decision`，且覆盖后仍继续经过 `apply_dry_run_decision_controls` 与 `apply_entry_gates`（`:280-311`） | 溯源要记**两段**：替换前主决策、替换后通道决策，以及二者各自被后续闸门改写的结果。只记一层会漏掉"通道被闸门降级"的路径 |
| D2 | 「RSI 实现存在但没进 live 评分链」（未给根因） | 指标名常量有**两份**：`src/indicators/indicator_spec.py:18` = `("MACD","CCI","BOLL","EMA","CVD","ATR")`（canonical）；`scripts/scaffold_ai300_framework.py:2092` = `("MACD","CCI","BOLL","RSI","CVD","ATR")`（03 期冻结）。失败用例断言的正是后者 | Task 2 的第一步不是"查接线"，而是**先钉死唯一名源**，否则 registry 没有基准 |
| D3 | 「live 用伪 CVD 近似」 | `volume_flow_score`（`src/signals/entry_chain_features.py:282-293`）只返回 `{0.0, 0.2, 0.5, 1.0}`；`component_points = clamp(score,0,1) × weight`（`src/signals/entry_chain_scoring.py:86-90`）→ 权重 18 的 `flow_cvd_confirmation` 实际只可能取 `{0, 3.6, 9.0, 18.0}` | 该分量**只有 3 个有效档位**（0 仅在 bars<6 时出现），ablation 的统计功效极低。这条要写进 registry 备注，避免 P1 用 18 分的名义自由度设计实验 |
| D4 | 把 `regime_overlay` / `score_core` 的 `ValueError` 列为待修漂移 | 二者**已是** `EntryChainConfig` 合法字段（`src/signals/entry_chain_config.py:246,251`），当前配置也含这两个键 | 重启前的 `unknown entry-chain config keys` 属**时点差异**，不是现存缺陷。P0 不要为它安排工时，只在漂移表登记 |
| D5 | §9.4 把"统一出场参数"当成改造工程 | `PaperExitConfig` 已存在且可注入（`src/observability/paper_trading.py:83,156,162`）；TP 与持仓上限是模块级常量（`TP_LEVELS` L22 = `(1.2,2.0,3.0)`、`MAX_HOLD_BARS` L19 = `32`），回测侧是函数默认（`src/backtest/lifecycle_exit.py:30-32` = `(1.0,2.0,3.0)` / `16`） | Task 7 只需把常量收进 `ExitSpec` 并加同构测试，**不需要重构出场逻辑**。风险点不在代码量，而在"改了回测默认值会让历史回测结论失效"，故必须显式标注版本 |
| D6 | 未提 | 工作树含 8 个已改文件（含 `run_live_dry_run.py` 与 3 个测试文件） | 不先冻结基线，任何"回归"都无法归因。Task 0 是硬前置 |

### 0.2 本计划引用的已核实锚点（Codex 可直接按此定位，若不符以源码为准）

| 锚点 | 位置 | 内容 |
|---|---|---|
| 配置加载 | `scripts/run_live_dry_run.py:115` | `config = load_entry_chain_config(args.config)` |
| 通道替换 | `scripts/run_live_dry_run.py:256-272` | 无条件调用 + 覆盖 `decision` |
| 声明式闸门 | `scripts/run_live_dry_run.py:304-311`、定义 `:1138` | `apply_entry_gates` 调用与定义 |
| 符号解析 | `scripts/run_live_dry_run.py:2301-2318` | CLI `--symbols` 优先；`market_cap_rank` 动态解析 |
| 启动日志 | `scripts/run_live_dry_run.py:3025,3043` | `orders_submitted=0` 与 `进程启动` 行 |
| 架构短路 | `src/signals/entry_chain_scoring.py:54-70` | fib_pa 先命中，EMA 次之，动态权重殿后 |
| 分量计分 | `src/signals/entry_chain_scoring.py:86-90` | `clamp(score,0,1) × weight` |
| 未知键拒绝 | `src/signals/entry_chain_config.py:253-258` | `from_mapping` 抛 `ValueError` |
| 仓位三 cap | `src/signals/entry_chain.py:735-758` | raw / leveraged / remaining → min |
| 出场常量 | `src/observability/paper_trading.py:19,22,23` | `MAX_HOLD_BARS=32`、`TP_LEVELS=(1.2,2.0,3.0)`、`TP_FRACTIONS=(0.40,0.35,0.25)` |
| 出场配置类 | `src/observability/paper_trading.py:83` | `PaperExitConfig` |
| 回测出场默认 | `src/backtest/lifecycle_exit.py:30-32` | `(1.0,2.0,3.0)` / `16` |
| 伪 CVD | `src/signals/entry_chain_features.py:282-293` | `volume_flow_score` 四档取值 |
| 指标名（canonical） | `src/indicators/indicator_spec.py:18` | 含 EMA、无 RSI |
| 指标名（scaffold） | `scripts/scaffold_ai300_framework.py:2092` | 含 RSI、无 EMA |
| 指标描述器 | `scripts/describe_indicator_rules.py:13-24,29` | 从 canonical 模块 import |

---

## 1. 执行纪律（不可协商）

1. **不改策略参数**：`configs/` 下任何数值、权重、阈值、杠杆、TP、`dry_run_symbols`、`post_close_delay`、`target_tier` 一律不动。P0 允许的配置改动只有"新增纯元数据键"，且必须同步 `tests/test_dry_run_configs.py`。
2. **不碰交易路径**：`src/api/binance_client.py`（真实路径；`src/exchange/` 下没有这个文件）、任何真实下单代码、`exchange_mutation_enabled` 均为禁区。
3. **行为等价优先**：P0 全程**不切换任何默认值**（出场口径只登记不切换）。每个 Task 都必须能用「同一输入 → 同一字段级输出（新增键除外）」证明行为未变。
4. **只加观测，不改判据**：新增字段写 payload / 日志 / 文件，不得参与 action、杠杆、闸门判定。
5. **数字只从事件流来**：任何盈亏汇总按 `position_id` 聚合 `PAPER_CLOSE`/`PAPER_REDUCE`；禁止跨天累加 `paper_summary.json` 计数器。
6. **单一权威口径**：`net_pnl_full`。`net_pnl` 仅并列展示，`realized_margin_pnl` / `margin_pnl` 带 `deprecated_leverage_double_count`，禁止作为结论依据。
7. **每 Task 一个 commit**，commit body 必须贴验收命令输出。
8. **一次一个实现者**：不并行派发改同一文件的 Task。

---

## 2. 需求追溯矩阵

| 你的核心方向 | 落到哪个 Task | 完成判据 |
|---|---|---|
| 1 盈利质量（单笔占 97.59%） | Task 3（对账回归锁死基数）+ P1-E1（集中度敏感性） | 33.762404 可一键复算；剔 top1 后数值进入固定报告 |
| 2 指标体系（MACD/BOLL/RSI/真 CVD 接线） | Task 2 | 每个指标有唯一状态；名源唯一；伪 CVD 有独立命名 |
| 3 决策架构（fib_pa/EMA/四象限/Q1/Gate 互相覆盖） | Task 4 + Task 5 | 架构单值可解析并打印；替换/闸门改写两段留痕 |
| 4 仓位与风控（统一计算/杠杆/暴露/风险预算） | Task 6 | 三 cap 与 binding 全字段入 trace；min 不变量有测试 |
| 5 出场优化（paper vs backtest 参数） | Task 7 | 同构测试防漂移；差异显式化为两个具名 spec |
| 6 实验验证（单变量/滚动/Block Bootstrap/成本压力） | P1（E1/E4/E6/E7） | 每个实验有预登记表与 INCONCLUSIVE 规则 |
| （基础）可复现 | Task 0 + Task 1 | 每次运行有 manifest；基线可归因 |

---

## 3. Task 0：基线冻结与可归因起点

**目的：** 让后续每个 P0 commit 的 diff 可归因。不冻结基线，Task 1-7 的任何"测试变红"都分不清是自己引入的还是既有脏改动导致的。

**Files:**
- Create: `docs/audit/2026-11-09-p0-baseline.md`
- 不修改任何代码

**Step 1: 记录机器现状**

```bash
cd D:/AIDCA/AI300-fwdlib
mkdir -p docs/audit
git rev-parse --short HEAD
git branch --show-current
git status --porcelain
git diff --stat
```

把输出原样贴进 `docs/audit/2026-11-09-p0-baseline.md`。

**Step 2: 跑测试基线并记录**

```bash
.venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/test_verify_five_factor_orthogonality.py 2>&1 | tail -15
```

Expected: `1 failed, 870 passed`。若数量不同，**停止并记录**，说明基线已变，先查清原因再继续。

**Step 3: 记录配置哈希**

```bash
.venv/Scripts/python.exe -c "
import hashlib,pathlib
for p in sorted(pathlib.Path('configs').glob('entry_chain*.json')):
    print(hashlib.sha256(p.read_bytes()).hexdigest()[:16], p.name)
"
```

**Step 4: 建工作分支（不改动既有改动）**

```bash
git switch -c p0-governance 2>/dev/null || git switch p0-governance
```

分支已存在时复用，不要 `switch -c` 硬撞（第二次执行会报 `already exists` 中断）。

**Step 5: 基线 commit（仅新增审计文件）**

```bash
git add docs/audit/2026-11-09-p0-baseline.md docs/plans/2026-11-09-p0-governance.md
git commit -m "docs(p0): 冻结 2026-11-09 基线（git 状态、pytest 1F/870P、配置哈希）"
```

**Step 6: 既有脏改动的处置（需人工一句话确认）**

两条路，二选一，**默认走 A**：

- **A（默认，推荐）**：把既有改动单独提交，使 P0 diff 干净。**逐条 add，禁止 `git add -A`**（`logs_parallel/` 约 12MB 且未被 `.gitignore` 覆盖，`git ls-files logs` 为 0 说明 `logs/` 已忽略、但 `logs_parallel/` 没有）：

  ```bash
  echo "logs_parallel/" >> .gitignore
  git add .gitignore
  git add CODEBUDDY.md configs/entry_chain.dry_run_fib_pa_v1.json \
          scripts/run_live_dry_run.py scripts/vps_dry_run_healthcheck.py \
          tests/test_dry_run_configs.py tests/test_entry_chain_config.py \
          tests/test_live_dry_run.py
  git add -u configs/entry_chain.dry_run.json
  git add docs/2026-10-20-restructuring-plan-v2-review.md \
          docs/2026-10-31-paper-run-review-and-recommendations.md \
          docs/AI300_strategy_optimization_advice.md \
          "docs/AI300_策略指标因子与决策逻辑_评审稿_20261108.md" \
          docs/analysis/2026-10-31_to_11-08_loss_attribution.md
  git commit -m "chore: 冻结 P0 前的机器现状快照（含 10-31 以来的工作树改动）"
  ```

  有意**不入库**：`configs/entry_chain.dry_run - 副本.json`（与 conservative 完全相同的备份）与 `configs/trading_config_fund_flow.json`（来源未确认）。它们保持 untracked，不会被 `git diff` 计入，也不会污染后续 `configs/entry_chain*.json` 的批量读取。

  优点：后续每个 P0 commit 只含自己的改动；缺点：把未审改动一起入库（可用单个 `git revert` 撤销）。
- **B**：`git stash push -u -m "pre-p0-wip"`，P0 完成后 `git stash pop`。
  优点：不动既有工作；缺点：P0 期间无法验证"脏改动 + P0"的组合行为，且 pop 易冲突。

只有 A/B 都无法接受时才停止。**不要**用 `git checkout --` 或 `git reset --hard` 丢弃任何既有改动。

**Step 7: 记录 BASE_SHA（后续验收要用）**

```bash
BASE=$(git rev-parse HEAD)
printf '\n## BASE_SHA\n\nBASE_SHA=%s\n' "$BASE" >> docs/audit/2026-11-09-p0-baseline.md
git add docs/audit/2026-11-09-p0-baseline.md
git commit -m "docs(p0): 记录 BASE_SHA（P0 起点）"
```

为什么不用 `HEAD~7`：只要 Task 1–7 之间出现任何一次修复 commit，`HEAD~7` 就会指错地方，"configs 零改动"的校验会随机失效。固定 SHA 才可判定。

**TDD 豁免说明：** Task 0 是纯记录任务，不产任何代码，故没有"先写失败测试"这一步。它的产出（基线文档 + BASE_SHA）是后续 7 个 Task 能被归因的前提。

**验收：** `docs/audit/2026-11-09-p0-baseline.md` 非空且含基线四段输出与 `BASE_SHA=`；分支为 `p0-governance`。

> 状态：DONE / 2026-11-09 / `0bd66ff（含基线 commit 36e2f0c、现状快照 e1e3b74）`

---

## 4. Task 1：Run Manifest（运行事实单一来源）

**目的：** 每次 dry-run / 回测启动即落盘一份不可变 `run_manifest.json`，把"到底跑了什么"从人工记忆变成文件。

**Files:**
- Create: `src/observability/run_manifest.py`
- Create: `tests/test_run_manifest.py`
- Modify: `scripts/run_live_dry_run.py`（仅在启动段追加写盘，约 `:115` 之后与 `:3043` 附近）

**Step 1: 写失败测试**

`tests/test_run_manifest.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.observability.run_manifest import (
    MANIFEST_SCHEMA_VERSION,
    RunManifest,
    build_run_manifest,
    git_state,
    sha256_file,
)

ROOT = Path(__file__).resolve().parents[1]


def _manifest(tmp_path: Path, config_text: str = '{"a": 1}', **overrides) -> RunManifest:
    config_path = tmp_path / "cfg.json"
    config_path.write_text(config_text, encoding="utf-8")
    kwargs = dict(
        root=ROOT,
        config_path=config_path,
        resolved_config={"a": 1},
        cli_args={"config": str(config_path)},
        target_tier="conservative",
        post_close_delay_seconds=10.0,
        kline_align=True,
        base_timeframe_seconds=900,
        universe_source="cli",
        universe_version=None,
        resolved_symbols=("BTCUSDT", "ETHUSDT"),
        pnl_schema_version=2,
        pnl_accounting_mode="notional_primary_margin_reporting",
        fee_bps=5.0,
        slippage_bps=5.0,
        exit_mode="legacy",
        paper_or_backtest_mode="paper",
        started_at_utc="2026-11-09T02:00:00Z",
    )
    kwargs.update(overrides)
    return build_run_manifest(**kwargs)


def test_config_sha_is_content_based(tmp_path):
    a = tmp_path / "a.json"
    a.write_text('{"x": 1}', encoding="utf-8")
    b = tmp_path / "b.json"
    b.write_text('{"x": 1}', encoding="utf-8")
    assert sha256_file(a) == sha256_file(b)


def test_config_sha_changes_with_content(tmp_path):
    a = tmp_path / "a.json"
    a.write_text('{"x": 1}', encoding="utf-8")
    first = sha256_file(a)
    a.write_text('{"x": 2}', encoding="utf-8")
    assert sha256_file(a) != first


def test_run_id_embeds_config_hash(tmp_path):
    manifest = _manifest(tmp_path)
    assert manifest.run_id.endswith(manifest.config_sha256[:8])
    assert manifest.run_id.startswith("20261109T020000Z")


def test_run_id_changes_when_config_changes(tmp_path):
    first = _manifest(tmp_path, '{"a": 1}')
    second = _manifest(tmp_path, '{"a": 2}')
    assert first.run_id != second.run_id


def test_manifest_has_all_required_fields(tmp_path):
    payload = _manifest(tmp_path).to_dict()
    required = {
        "run_id", "started_at_utc", "ended_at_utc", "git_commit", "git_branch",
        "working_tree_dirty", "config_path", "config_sha256", "resolved_config",
        "cli_args", "target_tier", "post_close_delay_seconds", "kline_align",
        "base_timeframe_seconds", "universe_source", "universe_version",
        "resolved_symbols", "pnl_schema_version", "pnl_accounting_mode",
        "fee_bps", "slippage_bps", "exit_mode", "paper_or_backtest_mode",
    }
    assert required <= set(payload)
    assert payload["schema_version"] == MANIFEST_SCHEMA_VERSION


def test_write_roundtrip(tmp_path):
    manifest = _manifest(tmp_path)
    target = manifest.write(tmp_path / "out" / "run_manifest.json")
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["run_id"] == manifest.run_id
    assert loaded["resolved_symbols"] == ["BTCUSDT", "ETHUSDT"]


def test_write_refuses_different_config_hash(tmp_path):
    first = _manifest(tmp_path, '{"a": 1}')
    target = first.write(tmp_path / "run_manifest.json")
    second = _manifest(tmp_path, '{"a": 2}', started_at_utc="2026-11-09T02:00:00Z")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        second.write(target)


def test_git_state_reports_repo(tmp_path):
    state = git_state(ROOT)
    assert set(state) == {"git_commit", "git_branch", "working_tree_dirty"}
    assert state["git_commit"]
```

**Step 2: 跑测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_run_manifest.py -q
```

Expected: `ModuleNotFoundError: No module named 'src.observability.run_manifest'`。

**Step 3: 写实现**

`src/observability/run_manifest.py`:

```python
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

MANIFEST_SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def git_state(root: str | Path) -> dict[str, Any]:
    base = Path(root)
    status = _git(base, "status", "--porcelain")
    return {
        "git_commit": _git(base, "rev-parse", "--short", "HEAD"),
        "git_branch": _git(base, "rev-parse", "--abbrev-ref", "HEAD"),
        "working_tree_dirty": None if status is None else bool(status),
    }


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    started_at_utc: str
    ended_at_utc: str | None
    git_commit: str | None
    git_branch: str | None
    working_tree_dirty: bool | None
    config_path: str
    config_sha256: str
    resolved_config: Mapping[str, Any]
    cli_args: Mapping[str, Any]
    target_tier: str
    post_close_delay_seconds: float
    kline_align: bool
    base_timeframe_seconds: int
    universe_source: str
    universe_version: str | None
    resolved_symbols: Sequence[str]
    pnl_schema_version: int
    pnl_accounting_mode: str
    fee_bps: float
    slippage_bps: float
    exit_mode: str
    paper_or_backtest_mode: str
    schema_version: int = MANIFEST_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = json.loads(target.read_text(encoding="utf-8"))
            if existing.get("config_sha256") != self.config_sha256:
                raise ValueError(
                    f"refusing to overwrite run manifest with different config hash: {target}"
                )
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return target


def build_run_manifest(
    *,
    root: str | Path,
    config_path: str | Path,
    resolved_config: Mapping[str, Any],
    cli_args: Mapping[str, Any],
    target_tier: str,
    post_close_delay_seconds: float,
    kline_align: bool,
    base_timeframe_seconds: int,
    universe_source: str,
    universe_version: str | None,
    resolved_symbols: Sequence[str],
    pnl_schema_version: int,
    pnl_accounting_mode: str,
    fee_bps: float,
    slippage_bps: float,
    exit_mode: str,
    paper_or_backtest_mode: str,
    started_at_utc: str | None = None,
    ended_at_utc: str | None = None,
) -> RunManifest:
    started = started_at_utc or utc_now_iso()
    config_sha = sha256_file(config_path)
    state = git_state(root)
    return RunManifest(
        run_id=f"{started.replace('-', '').replace(':', '')}-{config_sha[:8]}",
        started_at_utc=started,
        ended_at_utc=ended_at_utc,
        git_commit=state["git_commit"],
        git_branch=state["git_branch"],
        working_tree_dirty=state["working_tree_dirty"],
        config_path=str(config_path),
        config_sha256=config_sha,
        resolved_config=dict(resolved_config),
        cli_args=dict(cli_args),
        target_tier=target_tier,
        post_close_delay_seconds=float(post_close_delay_seconds),
        kline_align=bool(kline_align),
        base_timeframe_seconds=int(base_timeframe_seconds),
        universe_source=universe_source,
        universe_version=universe_version,
        resolved_symbols=tuple(resolved_symbols),
        pnl_schema_version=int(pnl_schema_version),
        pnl_accounting_mode=pnl_accounting_mode,
        fee_bps=float(fee_bps),
        slippage_bps=float(slippage_bps),
        exit_mode=exit_mode,
        paper_or_backtest_mode=paper_or_backtest_mode,
    )
```

**Step 4: 跑测试确认通过**

```bash
.venv/Scripts/python.exe -m pytest tests/test_run_manifest.py -q
```

Expected: `8 passed`。

**Step 5: 接入主循环（只写文件，不改判定）**

**路径必须复用既有约定**，不要自己另起一层：`scripts/run_live_dry_run.py:2279-2289` 的 `resolve_output_dir(args, timestamp=...)` 返回 `<log_root>/<YYYY-MM>/<YYYY-MM-DD>`。所以落点是：

```python
out_dir = resolve_output_dir(args, timestamp=startup_ts)
manifest.write(out_dir / f"run_manifest-{manifest.run_id}.json")
```

- 文件名带 `run_id`：同一天换配置重启时是新文件，不会撞上"同路径不同哈希"的 raise。
- 写盘时机：`run()` 内、符号解析（`:2300-2318`）**之后**一次，因为 manifest 需要 `resolved_symbols`。
- `resolved_config` 用 `dataclasses.asdict(config)`。
- `exit_mode` 取 `config.paper_exit_mode`。
- `fee_bps` / `slippage_bps` 从 `src.observability.paper_trading.FEE_BPS` / `SLIPPAGE_BPS` 导入，**不要写字面量 5.0**。
- `pnl_schema_version` 从 `paper_trading.PNL_SCHEMA_VERSION` 取值（已存在，`paper_trading.py:30`）。
- **`pnl_accounting_mode` 目前没有模块级常量**，同一字面量 `"notional_primary_margin_reporting"` 在 `paper_trading.py:276,425,477,530` 抄了**四处**（已逐行核实，不是三处）。先在 `:30` 旁新增：

  ```python
  PNL_ACCOUNTING_MODE = "notional_primary_margin_reporting"
  ```

  把**四处**字面量全部替换为 `PNL_ACCOUNTING_MODE`，manifest 再从该常量导入。这是纯去重，输出字符串逐字节不变，但必须同时加一条测试：

  ```python
  def test_pnl_accounting_mode_is_single_sourced():
      from src.observability import paper_trading
      assert paper_trading.PNL_ACCOUNTING_MODE == "notional_primary_margin_reporting"
      source = (ROOT / "src/observability/paper_trading.py").read_text(encoding="utf-8")
      assert source.count('"notional_primary_margin_reporting"') == 1
  ```

  最后一条断言的含意是：字面量只允许出现在常量定义那一行，其余位置必须引用常量。
- **写盘失败策略：fail-open，但必须响**。用 `except OSError` 捕获后写 `print(f"RUN_MANIFEST_WRITE_FAILED: {exc}")` 到日志并继续；**不要**让一次磁盘/权限问题杀掉 dry-run 主循环。`RunManifest.write` 内部的 `ValueError`（同路径不同哈希）不捕获——那是真错，但按上面带 `run_id` 的文件名，正常不会触发。

  这与"可复现优先"不矛盾：manifest 缺失时，`DRY_RUN` 日志里会留下 `RUN_MANIFEST_WRITE_FAILED`，这一轮的结论按 `INCONCLUSIVE` 处理，而不是假装有 manifest。

**Step 6: 验证行为未变**

```bash
.venv/Scripts/python.exe -m pytest tests/test_live_dry_run.py tests/test_run_manifest.py -q
```

Expected: 全绿。若 `test_live_dry_run.py` 变红，说明接入点影响了主循环控制流，回退重做。

**Step 7: Commit**

```bash
git add src/observability/run_manifest.py tests/test_run_manifest.py scripts/run_live_dry_run.py
git commit -m "feat(obs): 新增 run_manifest 落盘（运行事实单一来源，不改任何判定）"
```

**验收：** `tests/test_run_manifest.py` 全绿；`tests/test_live_dry_run.py` 全绿；主循环中 `run_manifest.json` 的路径可见于启动日志。

> 状态：DONE / 2026-11-09 / `0dc4922`

---

## 5. Task 2：指标接线矩阵（唯一名源 + 状态登记）

**目的：** 回答"MACD / BOLL / RSI / 真 CVD 到底接没接进当前评分链"，并把答案固化成可机检的注册表，而不是文档里的一句话。

**Files:**
- Modify: `tests/test_describe_indicator_rules.py`（修正断言到 canonical 名源）
- Create: `tests/test_indicator_name_sources.py`
- Create: `src/signals/feature_registry.py`
- Create: `tests/test_feature_registry.py`

**Step 1: 先确认名源意图（不改代码，只查证）**

```bash
git log --oneline -8 -- src/indicators/indicator_spec.py
git log --oneline -8 -- scripts/scaffold_ai300_framework.py
grep -n "INDICATOR_NAMES" src/indicators/indicator_spec.py scripts/scaffold_ai300_framework.py
```

判据：若 `indicator_spec.py` 的 EMA 版本晚于 scaffold 的 RSI 版本，则 **canonical = EMA 版**，scaffold 属 03 期冻结契约。把两条 commit 与判断写进 Step 6 的漂移登记。

**Step 2: 修正陈旧断言（两处，不是一处）**

`tests/test_describe_indicator_rules.py` 里有两条断言锁的是 03 期的 RSI 版本，必须同时改，否则改完第一条会立刻在第二条上继续红：

```python
# 第 1 处
    assert payload["indicator_names"] == ["MACD", "CCI", "BOLL", "EMA", "CVD", "ATR"]

# 第 2 处：15m 启用集里 RSI 已被 EMA 顶替，且 EMA 占据原来的第一位
    assert payload["timeframe_indicator_map"]["15m"] == ["EMA", "MACD", "CVD", "BOLL"]
```

已核实描述器实际输出：`indicator_names = ['MACD','CCI','BOLL','EMA','CVD','ATR']`、`15m = ['EMA','MACD','CVD','BOLL']`、`responsibilities` 中已无 `RSI` 键（故不存在第三条 RSI 断言）。**只改测试，不改 spec**——spec 是 canonical。

**Step 3: 新增名源守卫测试**

`tests/test_indicator_name_sources.py`:

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.indicators.indicator_spec import INDICATOR_NAMES

ROOT = Path(__file__).resolve().parents[1]

# 03 期冻结契约与当前 canonical 规格的唯一允许差异。
# 新增差异必须先改这里，再改实现——防止名源再次静默分叉。
KNOWN_SCAFFOLD_NAME_DIVERGENCE = ({"RSI"}, {"EMA"})


def test_describe_uses_canonical_names():
    result = subprocess.run(
        [sys.executable, "scripts/describe_indicator_rules.py"],
        cwd=str(ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert tuple(payload["indicator_names"]) == INDICATOR_NAMES


def test_live_spec_excludes_rsi_includes_ema():
    assert "EMA" in INDICATOR_NAMES
    assert "RSI" not in INDICATOR_NAMES


def test_scaffold_divergence_is_declared():
    import re

    source = (ROOT / "scripts" / "scaffold_ai300_framework.py").read_text(encoding="utf-8")
    match = re.search(r"^INDICATOR_NAMES\s*=\s*\(([^)]*)\)", source, re.MULTILINE)
    assert match is not None, "scaffold 中未找到 INDICATOR_NAMES"
    scaffold_names = tuple(
        part.strip().strip("\"'") for part in match.group(1).split(",") if part.strip()
    )

    only_scaffold = set(scaffold_names) - set(INDICATOR_NAMES)
    only_canonical = set(INDICATOR_NAMES) - set(scaffold_names)
    assert (only_scaffold, only_canonical) == KNOWN_SCAFFOLD_NAME_DIVERGENCE
```

**为什么用正则而不是 import：** 已实测确认，`scaffold_ai300_framework.py:2092` 的 `INDICATOR_NAMES` **不在模块顶层**——它位于一段被生成的源码模板字符串内部（`ast.parse(...).body` 里找不到该 Assign，`src.count("INDICATOR_NAMES") == 4` 但模块级赋值 0 处）。这有两个后果：一是 `from scripts.scaffold_ai300_framework import INDICATOR_NAMES` 根本拿不到它；二是这条常量属于**生成器模板的冻结契约**，不应按 live 规格去改。正则按行首锚定是该文件唯一稳定的读取方式。
```

**Step 4: 写 registry 失败测试**

`tests/test_feature_registry.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from src.signals.feature_registry import (
    FIB_PA_COMPONENTS,
    FEATURE_REGISTRY,
    FeatureStatus,
    assert_registry_consistent,
)

ROOT = Path(__file__).resolve().parents[1]


def test_component_weights_sum_to_100():
    total = sum(entry.weight or 0.0 for entry in FEATURE_REGISTRY if entry.weight)
    assert total == pytest.approx(100.0)


def test_every_component_is_live_with_read_point():
    for entry in FEATURE_REGISTRY:
        if entry.weight:
            assert entry.status is FeatureStatus.LIVE_FEATURE, entry.name
            assert entry.read_point, entry.name
            assert entry.read_point_symbol, entry.name


def test_read_points_are_real():
    """锚点必须**精确到行**：该行必须出现该符号。

    这是本计划唯一的防腐坏机关。行号漂了，测试就红，逼你回来改 registry，
    而不是让"接线矩阵"慢慢变成一份过期文档。
    """
    for entry in FEATURE_REGISTRY:
        if not entry.read_point:
            continue
        path_part, _, line_part = entry.read_point.partition(":")
        target = ROOT / path_part
        assert target.exists(), f"{entry.name}: {path_part} 不存在"
        assert line_part.isdigit(), f"{entry.name}: read_point 缺行号"
        lines = target.read_text(encoding="utf-8").split("\n")
        line_no = int(line_part)
        assert 1 <= line_no <= len(lines), f"{entry.name}: 行号 {line_no} 越界"
        assert entry.read_point_symbol in lines[line_no - 1], (
            f"{entry.name}: {entry.read_point} 该行不含 {entry.read_point_symbol!r}，"
            f"实际内容={lines[line_no - 1].strip()!r}"
        )


def test_rsi_is_not_live():
    rsi = next(e for e in FEATURE_REGISTRY if e.name == "rsi14")
    assert rsi.status is FeatureStatus.IMPLEMENTED
    assert rsi.read_point is None


def test_macd_and_boll_are_spec_only():
    for name in ("macd", "boll"):
        entry = next(e for e in FEATURE_REGISTRY if e.name == name)
        assert entry.status is FeatureStatus.SPEC_ONLY


def test_pseudo_cvd_is_named_distinctly():
    pseudo = next(e for e in FEATURE_REGISTRY if e.name == "flow_cvd_confirmation")
    assert pseudo.source_field == "candle_signed_volume_flow"
    real = next(e for e in FEATURE_REGISTRY if e.name == "taker_flow_cvd")
    assert real.status is FeatureStatus.COMPUTED
    assert real.source_field == "taker_buy_base_volume"


def test_registry_consistency_helper():
    assert_registry_consistent()


def test_fib_pa_component_names_match_scoring_module():
    from src.signals.entry_chain_scoring import FIB_PA_WEIGHTS

    assert set(FIB_PA_COMPONENTS) == set(FIB_PA_WEIGHTS)
```

**Step 5: 写 registry 实现**

`src/signals/feature_registry.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FeatureStatus(str, Enum):
    SPEC_ONLY = "SPEC_ONLY"          # 规格声明存在，无 live 计算
    IMPLEMENTED = "IMPLEMENTED"      # 代码可算，未接入 live
    COMPUTED = "COMPUTED"            # live 周期在算，但不进评分
    LOGGED_ONLY = "LOGGED_ONLY"      # 写日志/影子，不影响决策
    LIVE_FEATURE = "LIVE_FEATURE"    # 进 total_score
    RISK_INPUT = "RISK_INPUT"        # 进风险/仓位
    DISABLED = "DISABLED"            # 显式关闭


@dataclass(frozen=True)
class FeatureEntry:
    name: str
    kind: str
    status: FeatureStatus
    weight: float | None = None
    read_point: str | None = None
    read_point_symbol: str | None = None
    source_field: str | None = None
    timeframe: str | None = None
    note: str = ""


FIB_PA_COMPONENTS = (
    "trend_ema_context",
    "flow_cvd_confirmation",
    "cci_momentum_quality",
    "price_action_structure",
    "fibonacci_location",
    "risk_reward_geometry",
)

FEATURE_REGISTRY: tuple[FeatureEntry, ...] = (
    FeatureEntry(
        name="trend_ema_context",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=20.0,
        read_point="src/signals/entry_chain_features.py:116",
        read_point_symbol="trend_ema_context_score",
        timeframe="15m/1h",
        note="EMA200 方向闸在 soft 模式下只扣分，hard 模式才 veto。",
    ),
    FeatureEntry(
        name="flow_cvd_confirmation",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=18.0,
        read_point="src/signals/entry_chain_features.py:282",
        read_point_symbol="volume_flow_score",
        source_field="candle_signed_volume_flow",
        timeframe="15m",
        note=(
            "不是真主动买卖流。取值仅 {0.0,0.2,0.5,1.0}，乘权重 18 后只可能得 "
            "{0,3.6,9.0,18.0}，实际只有 3 个有效档位。"
        ),
    ),
    FeatureEntry(
        name="cci_momentum_quality",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=14.0,
        read_point="src/signals/entry_chain_features.py:108",
        read_point_symbol='"cci_momentum_quality"',
        timeframe="15m",
        note="离散档位 14/10/7/3/0 先除 14 归一到 0-1，再乘权重。",
    ),
    FeatureEntry(
        name="price_action_structure",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=22.0,
        read_point="src/signals/entry_chain_features.py:109",
        read_point_symbol='"price_action_structure"',
        timeframe="15m",
        note="PA 原始分 0-22，除 22 归一到 0-1。",
    ),
    FeatureEntry(
        name="fibonacci_location",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=18.0,
        read_point="src/signals/entry_chain_features.py:110",
        read_point_symbol='"fibonacci_location"',
        timeframe="15m",
        note="交易层 fib 参数取函数默认值，配置键未被读取。",
    ),
    FeatureEntry(
        name="risk_reward_geometry",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=8.0,
        read_point="src/signals/entry_chain_features.py:111",
        read_point_symbol='"risk_reward_geometry"',
        timeframe="15m",
        note="净 TP1 R 的计算在 :164-221，net_tp1_r 于 :172 求得。",
    ),
    FeatureEntry(
        name="rsi14",
        kind="indicator",
        status=FeatureStatus.IMPLEMENTED,
        read_point=None,
        timeframe="15m",
        note="src/indicators/rsi.py 可算；_build_rsi_result 无调用点，live 评分链不读 RSI。",
    ),
    FeatureEntry(
        name="macd",
        kind="indicator",
        status=FeatureStatus.SPEC_ONLY,
        timeframe="15m",
        note="仅存在于 src/indicators/indicator_spec.py 的规格与 indicator_engine 的计算；不进 fib_pa 六分量。",
    ),
    FeatureEntry(
        name="boll",
        kind="indicator",
        status=FeatureStatus.SPEC_ONLY,
        timeframe="15m",
        note="同上；无 live 读取点。",
    ),
    FeatureEntry(
        name="taker_flow_cvd",
        kind="indicator",
        status=FeatureStatus.COMPUTED,
        read_point="src/indicators/cvd.py:6",
        read_point_symbol="def cvd",
        source_field="taker_buy_base_volume",
        timeframe="15m",
        note="真 CVD，用 klines[9]；live 评分不读它，评分用的是 candle_signed_volume_flow。",
    ),
    FeatureEntry(
        name="five_factor_shadow",
        kind="model",
        status=FeatureStatus.LOGGED_ONLY,
        read_point="src/signals/orthogonal_factors.py:491",
        read_point_symbol="shadow_total",
        note="只写 component_points_v2 与 meta，不参与 total_score/象限/通道/杠杆。",
    ),
    FeatureEntry(
        name="net_beta_exposure",
        kind="model",
        status=FeatureStatus.RISK_INPUT,
        read_point="src/risk/net_beta_exposure_model.py:28",
        read_point_symbol="static_v1_observation_only",
        note="命名即 observation_only；cap 值不参与下单阻断。",
    ),
    FeatureEntry(
        name="stress_simulation",
        kind="model",
        status=FeatureStatus.LOGGED_ONLY,
        read_point="src/risk/stress_simulator.py:8",
        read_point_symbol="def stress_decision",
        note="stress 的 action 无代码据此拦单。",
    ),
)


def assert_registry_consistent() -> None:
    names = [entry.name for entry in FEATURE_REGISTRY]
    if len(names) != len(set(names)):
        raise AssertionError("feature registry 存在重名")
    weighted = [entry for entry in FEATURE_REGISTRY if entry.weight]
    total = sum(entry.weight or 0.0 for entry in weighted)
    if abs(total - 100.0) > 1e-9:
        raise AssertionError(f"分量权重合计应为 100，实际 {total}")
    for entry in weighted:
        if entry.status is not FeatureStatus.LIVE_FEATURE:
            raise AssertionError(f"{entry.name} 有权重但状态不是 LIVE_FEATURE")


def registry_snapshot() -> list[dict[str, object]]:
    return [
        {
            "name": entry.name,
            "kind": entry.kind,
            "status": entry.status.value,
            "weight": entry.weight,
            "read_point": entry.read_point,
            "source_field": entry.source_field,
            "timeframe": entry.timeframe,
            "note": entry.note,
        }
        for entry in FEATURE_REGISTRY
    ]
```

**Step 6: 跑测试 + 登记漂移**

```bash
.venv/Scripts/python.exe -m pytest tests/test_feature_registry.py tests/test_indicator_name_sources.py tests/test_describe_indicator_rules.py -q
```

Expected: 全绿（原有 1 failed 消失）。

把 Step 1 的结论追加到 `docs/audit/2026-11-09-p0-baseline.md`，一节「指标名源分叉登记」：两份常量的位置、先后 commit、裁定（canonical=EMA 版；scaffold 为 03 期冻结）、以及 `KNOWN_SCAFFOLD_NAME_DIVERGENCE` 的存在理由。

**Step 7: Commit**

```bash
git add src/signals/feature_registry.py tests/test_feature_registry.py tests/test_indicator_name_sources.py tests/test_describe_indicator_rules.py docs/audit/2026-11-09-p0-baseline.md
git commit -m "feat(signals): 指标接线矩阵 + 唯一名源守卫；修正 03 期陈旧断言"
```

**验收：** pytest `0 failed`；registry 权重合计 100；RSI=IMPLEMENTED 且无 read_point；MACD/BOLL=SPEC_ONLY；真 CVD=COMPUTED 且与伪 CVD 命名分离。

> 状态：DONE / 2026-11-09 / `55e0b80`

---

## 6. Task 3：账本对账固化为回归测试

**目的：** 把"33.762404 这个数怎么来"锁进测试。以后谁改了 PnL 口径或成本摊分，测试立刻变红。

**TDD 豁免说明：** 这是 **characterization test（特征化/回归锁定测试）**——它描述的是"当前已发生的事实"，按定义**首次运行就应当通过**。若首次就红，说明基线事实与归因报告不符，此时应停下来核查，而不是改测试迁就代码。因此本 Task 没有"先写失败测试"这一步，这是有意豁免，不是遗漏。

**Files:**
- Create: `tests/test_ledger_reconciliation_window.py`

**Step 1: 写测试**

```python
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN_LEDGER_DIRS = [
    ROOT / "logs" / "2026-10" / "2026-10-31",
    *(ROOT / "logs" / "2026-11" / f"2026-11-{day:02d}" for day in range(1, 9)),
]
SUMMARY_PATH = ROOT / "logs" / "2026-11" / "2026-11-08" / "paper_summary.json"
EXIT_EVENTS = {"PAPER_REDUCE", "PAPER_CLOSE"}
EXPECTED_TOTAL_NET_PNL_FULL = 33.762404
EXPECTED_POSITIONS = 11

# 关键：logs/ 在 .gitignore 第 10 行，`git ls-files logs` 为 0 条。
# 干净 clone / CI 上没有账本数据，此时必须**整文件 skip**（记 INCONCLUSIVE），
# 而不是红——否则本 Task 在换机后永远无法通过。
pytestmark = pytest.mark.skipif(
    not SUMMARY_PATH.exists(),
    reason="需要本机 10-31→11-08 账本数据；缺失记 INCONCLUSIVE，不等于 PASS",
)


def _iter_events() -> list[dict]:
    events: list[dict] = []
    for directory in MAIN_LEDGER_DIRS:
        path = directory / "paper_trades.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _position_totals() -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for event in _iter_events():
        if event.get("event") in EXIT_EVENTS:
            totals[event["position_id"]] += float(event["net_pnl_full"])
    return dict(totals)


def test_position_count_matches_summary():
    totals = _position_totals()
    assert len(totals) == EXPECTED_POSITIONS


def test_total_net_pnl_full_matches_summary():
    totals = _position_totals()
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert sum(totals.values()) == pytest.approx(EXPECTED_TOTAL_NET_PNL_FULL, abs=1e-6)
    assert sum(totals.values()) == pytest.approx(
        float(summary["realized_notional_pnl"]), abs=1e-9
    )


def test_net_pnl_is_not_used_as_authoritative():
    totals: dict[str, float] = defaultdict(float)
    for event in _iter_events():
        if event.get("event") in EXIT_EVENTS:
            totals[event["position_id"]] += float(event["net_pnl"])
    assert sum(totals.values()) != pytest.approx(EXPECTED_TOTAL_NET_PNL_FULL, abs=1e-3)


def test_cross_day_summation_would_be_wrong():
    daily: list[float] = []
    for directory in MAIN_LEDGER_DIRS:
        path = directory / "paper_summary.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            daily.append(float(payload["realized_notional_pnl"]))
    assert len(daily) > 1
    assert sum(daily) != pytest.approx(EXPECTED_TOTAL_NET_PNL_FULL, abs=1e-6)


def test_deprecated_margin_field_is_not_the_authority():
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    margin = summary.get("realized_margin_pnl")
    if margin is None:
        pytest.skip("summary 未提供 realized_margin_pnl")
    assert float(margin) > EXPECTED_TOTAL_NET_PNL_FULL * 2
```

**Step 2: 跑测试**

```bash
.venv/Scripts/python.exe -m pytest tests/test_ledger_reconciliation_window.py -q
```

Expected: `5 passed`。若 `net_pnl_full` 字段名不符，先 `head -1` 看一条 `PAPER_CLOSE` 事件的实际键名再改测试，**不要改账本**。

**Step 3: Commit**

```bash
git add tests/test_ledger_reconciliation_window.py
git commit -m "test(ledger): 锁死 10-31→11-08 主账本对账口径（33.762404 / 11 position / 禁跨天求和）"
```

**验收：** 5 条断言全绿；`test_cross_day_summation_would_be_wrong` 明确禁掉跨天求和这条错误做法。

> 状态：DONE / 2026-11-09 / `0fea3bb`

---

## 7. Task 4：评分架构单值化

**目的：** 当前 `use_fib_pa_architecture` 与 `use_ema_architecture` 同时为 true，靠 `entry_chain_scoring.py:56-58` 的短路顺序"碰巧"选中 fib_pa。把它变成可解析、可打印、可断言的单值。

**Files:**
- Modify: `src/signals/entry_chain_scoring.py`（新增 `resolve_architecture`，`dynamic_weights` 委托）
- Create: `tests/test_scoring_architecture_resolution.py`

**Step 1: 写失败测试**

```python
from __future__ import annotations

from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config
from src.signals.entry_chain_scoring import FIB_PA_WEIGHTS, resolve_architecture


def test_both_flags_resolve_to_fib_pa_with_warning():
    cfg = EntryChainConfig(use_fib_pa_architecture=True, use_ema_architecture=True)
    name, reasons = resolve_architecture(cfg)
    assert name == "fib_pa"
    assert "ARCHITECTURE_FLAGS_BOTH_TRUE" in reasons


def test_ema_only_resolves_to_ema():
    cfg = EntryChainConfig(use_fib_pa_architecture=False, use_ema_architecture=True)
    name, reasons = resolve_architecture(cfg)
    assert name == "ema"
    assert "EMA_ARCHITECTURE_WEIGHTS" in reasons


def test_neither_resolves_to_base_or_dynamic():
    cfg = EntryChainConfig(use_fib_pa_architecture=False, use_ema_architecture=False)
    name, _ = resolve_architecture(cfg, atr_pct=0.01)
    assert name in {"base", "high_vol_dynamic", "low_vol_dynamic"}


def test_regime_shadow_config_resolves_to_fib_pa():
    cfg = load_entry_chain_config("configs/entry_chain.dry_run_regime_shadow.json")
    name, _ = resolve_architecture(cfg)
    assert name == "fib_pa"


def test_active_weights_match_fib_pa_table():
    cfg = EntryChainConfig(use_fib_pa_architecture=True, use_ema_architecture=True)
    name, _ = resolve_architecture(cfg)
    assert name == "fib_pa"
    assert FIB_PA_WEIGHTS["price_action_structure"] == 22.0
```

**Step 2: 跑测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_scoring_architecture_resolution.py -q
```

Expected: `ImportError: cannot import name 'resolve_architecture'`。

**Step 3: 改实现**

在 `src/signals/entry_chain_scoring.py` 中新增（并在 `dynamic_weights` 首行改为调用它）：

```python
def resolve_architecture(
    config: EntryChainConfig | None = None,
    atr_pct: float = 0.0,
) -> tuple[str, list[str]]:
    cfg = config or EntryChainConfig()
    reasons: list[str] = []
    if cfg.use_fib_pa_architecture and cfg.use_ema_architecture:
        reasons.append("ARCHITECTURE_FLAGS_BOTH_TRUE")
    if cfg.use_fib_pa_architecture:
        reasons.append("FIB_PA_ARCHITECTURE_WEIGHTS")
        return "fib_pa", reasons
    if cfg.use_ema_architecture:
        reasons.append("EMA_ARCHITECTURE_WEIGHTS")
        return "ema", reasons
    if atr_pct > cfg.high_vol_atr_pct:
        reasons.append("HIGH_VOL_DYNAMIC_WEIGHTS")
        return "high_vol_dynamic", reasons
    if atr_pct < cfg.low_vol_atr_pct:
        reasons.append("LOW_VOL_DYNAMIC_WEIGHTS")
        return "low_vol_dynamic", reasons
    reasons.append("BASE_WEIGHTS")
    return "base", reasons
```

`dynamic_weights` 改为先取 `name, reasons = resolve_architecture(cfg, atr_pct)`，再按 `name` 返回对应权重表，**保持原返回值签名不变**。

**Step 4: 把结果同时写进逐笔 payload（否则历史交易查不到）**

启动日志只解决"当前进程在跑什么架构"。要回答"**这笔**历史交易用的哪套架构"，必须落进决策记录。在 payload 组装处（`:271-282`）追加一行：

```python
decision_payload["active_architecture"] = architecture_name
decision_payload["active_architecture_reasons"] = architecture_reasons
```

只加键，不改判定。

**Step 5: 跑全量相关测试**

```bash
.venv/Scripts/python.exe -m pytest tests/test_scoring_architecture_resolution.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q
```

Expected: 全绿。

**Step 6: Commit**

```bash
git add src/signals/entry_chain_scoring.py scripts/run_live_dry_run.py tests/test_scoring_architecture_resolution.py
git commit -m "refactor(scoring): 架构解析单值化（双开关同时 true 时显式告警，行为不变）"
```

**验收：** 双 true 时返回 `fib_pa` 且带 `ARCHITECTURE_FLAGS_BOTH_TRUE`；启动日志可见 `active_architecture=fib_pa`。

> 状态：DONE / 2026-11-09 / `d44d7ef`

---

## 8. Task 5：决策溯源（主决策 / 通道 / 闸门两段留痕）

**目的：** 现在 `decision` 被 `q1_green_channel` 覆盖后，账本里看不出"这笔原本是什么信号、被谁替换、替换后又被谁降级"。补三个字段，不改任何判定。

**Files:**
- Create: `src/signals/decision_provenance.py`
- Create: `tests/test_decision_provenance.py`
- Modify: `scripts/run_live_dry_run.py:256-272`（覆盖处调用留痕函数）

**Step 1: 写失败测试**

```python
from __future__ import annotations

from src.signals.decision_provenance import annotate_replacement, decision_id


def _decision(**kwargs):
    base = {"symbol": "BTCUSDT", "timestamp": 1793889000, "side": "SHORT",
            "action": "DIRECT", "score": 89.25, "leverage": 4,
            "exit_mode": "legacy", "entry_channel": "main_direct"}
    base.update(kwargs)
    return base


def test_decision_id_is_stable():
    first = decision_id(_decision(), {"quadrant": "Q1"})
    second = decision_id(_decision(), {"quadrant": "Q1"})
    assert first == second


def test_accepts_decision_object():
    class Decision:
        symbol = "ETHUSDT"
        timestamp = 1793900000
        side = "LONG"
        action = "DIRECT"
        score = 85.0
        leverage = 2
        exit_mode = "legacy"
        entry_channel = "main_direct"

    payload = {"quadrant": "Q2"}
    assert decision_id(Decision(), payload) == "ETHUSDT:1793900000:LONG"
    _, merged = annotate_replacement(Decision(), payload, None, None)
    assert merged["decision_origin"] == "primary"


def test_snapshot_falls_back_to_payload_for_missing_fields():
    """真实 EntryChainDecision 没有 exit_mode/entry_channel/symbol，必须由 payload 兜底。"""
    base_decision = _decision()
    base_payload = {
        "quadrant": "Q1",
        "exit_mode": "legacy",
        "entry_channel": "main_direct",
    }
    new_decision = _decision(action="PROBE")
    new_payload = {"quadrant": "Q1"}
    _, merged = annotate_replacement(base_decision, base_payload, new_decision, new_payload)
    assert merged["replaced_snapshot"]["exit_mode"] == "legacy"
    assert merged["replaced_snapshot"]["entry_channel"] == "main_direct"


def test_replacement_records_before_and_after():
    base_decision = _decision(action="WATCH", score=71.0)
    base_payload = {"quadrant": "Q1", "entry_price": 100.0}
    new_decision = _decision(action="PROBE", score=88.0, leverage=1,
                             exit_mode="trend_capture",
                             entry_channel="q1_trend_launch")
    new_payload = {"quadrant": "Q1", "entry_price": 101.0}

    merged_decision, merged_payload = annotate_replacement(
        base_decision, base_payload, new_decision, new_payload,
        origin="q1_green_channel",
    )

    assert merged_decision is new_decision
    assert merged_payload["decision_origin"] == "q1_green_channel"
    assert merged_payload["replaced_decision_id"] == decision_id(base_decision, base_payload)
    snapshot = merged_payload["replaced_snapshot"]
    assert snapshot["action"] == "WATCH"
    assert snapshot["score"] == 71.0
    assert snapshot["quadrant"] == "Q1"
    assert snapshot["exit_mode"] == "legacy"


def test_no_replacement_leaves_origin_primary():
    decision = _decision()
    payload = {"quadrant": "Q1"}
    _, merged_payload = annotate_replacement(decision, payload, None, None)
    assert merged_payload["decision_origin"] == "primary"
    assert "replaced_decision_id" not in merged_payload


def test_replacement_does_not_mutate_inputs():
    base_decision = _decision()
    base_payload = {"quadrant": "Q1"}
    new_decision = _decision(action="PROBE")
    new_payload = {"quadrant": "Q2"}
    annotate_replacement(base_decision, base_payload, new_decision, new_payload)
    assert "decision_origin" not in base_payload
    assert "decision_origin" not in new_payload
```

**Step 2: 跑测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_decision_provenance.py -q
```

Expected: `ModuleNotFoundError`。

**Step 3: 写实现**

`src/signals/decision_provenance.py`:

```python
from __future__ import annotations

from typing import Any, Mapping

SNAPSHOT_FIELDS = (
    "action",
    "score",
    "side",
    "leverage",
    "exit_mode",
    "entry_channel",
)


def _field(obj: Any, name: str) -> Any:
    """同时支持 Mapping 与对象（主循环里的 decision 是 EntryChainDecision 数据类）。"""
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def decision_id(decision: Any, payload: Mapping[str, Any]) -> str:
    symbol = _field(decision, "symbol") or payload.get("symbol") or "UNKNOWN"
    timestamp = _field(decision, "timestamp") or payload.get("timestamp") or 0
    side = _field(decision, "side") or payload.get("side") or "NONE"
    return f"{symbol}:{int(timestamp)}:{side}"


def _snapshot(decision: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    """快照必须对 payload 兜底。

    真实的 EntryChainDecision（src/signals/entry_chain.py:63-75）只有
    action/side/score/weights/component_points/reasons/risk_allowed/leverage/
    max_symbol_exposure_pct/notional_hint/liquidity_ratio/metadata，
    **没有** symbol/timestamp/exit_mode/entry_channel——这四个只在 payload 里。
    不兜底的话 replaced_snapshot.exit_mode 在生产上恒为 None。
    """
    snapshot: dict[str, Any] = {}
    for field in SNAPSHOT_FIELDS:
        value = _field(decision, field)
        if value is None:
            value = payload.get(field)
        snapshot[field] = value
    snapshot["quadrant"] = payload.get("quadrant")
    return snapshot


def annotate_replacement(
    base_decision: Any,
    base_payload: Mapping[str, Any],
    new_decision: Any | None,
    new_payload: Mapping[str, Any] | None,
    *,
    origin: str = "q1_green_channel",
) -> tuple[Any, dict[str, Any]]:
    if new_decision is None or new_payload is None:
        merged = dict(base_payload)
        merged["decision_origin"] = "primary"
        return base_decision, merged

    merged = dict(new_payload)
    merged["decision_origin"] = origin
    merged["replaced_decision_id"] = decision_id(base_decision, base_payload)
    merged["replaced_snapshot"] = _snapshot(base_decision, base_payload)
    return new_decision, merged
```

`_field` 是必需的：主循环里 `decision` 是 `EntryChainDecision` 数据类（`src/signals/entry_chain.py:63`），不是 dict；直接 `.get()` 会 `AttributeError`。

**Step 4: 接入主循环（顺序必须照 `:256-311` 的真实结构，不能想当然）**

实测的控制流是：

```
:256  green_channel_decision = build_q1_green_channel_decision(base_decision=decision, ...)
:264  if green_channel_decision is not None:
:265      decision = apply_dry_run_decision_controls(green_channel_decision, ...)
:271      decision_payload = annotate_quadrant(enrich_decision_payload(decision.to_dict(), ...), config)
:283  else:  # q1 策略拒绝分支，同样从 decision.to_dict() 重建 payload
:299  decision, decision_payload = apply_experimental_quadrant_entry_rules(...)
:304  decision, decision_payload = apply_entry_gates(...)
:313  regime_overlay cap_decision 只降级、不平仓
```

注意 `:265` 的控件是**在分支内部**先跑的，`:271` 的 payload 由控件后的 `decision.to_dict()` 派生。所以**不能**"先 annotate 再 controls"——那会让 payload 与 decision 错位。

正确改法（三处小改，不碰任何判定函数内部）：

1. `:255` 之前保存原件：

   ```python
   primary_decision = decision
   primary_payload = dict(decision_payload)
   ```

2. `:282` 之后（即 `if` 分支内 payload 重建完毕）标注替换：

   ```python
   decision, decision_payload = annotate_replacement(
       primary_decision, primary_payload, decision, decision_payload,
       origin="q1_green_channel",
   )
   ```

   `else` 分支（`:283-298`）不替换，保持 `decision_origin="primary"`，不做标注。

3. 对后续三处"可能改写 action"的调用（`:299` 实验象限规则、`:304` 声明式闸门、`:313` overlay cap）用一个统一小包装，**不改这三个函数内部**：

   ```python
   def _record_gate_adjustment(before_decision, before_payload, after_decision, after_payload):
       before_action = before_decision.action
       after_action = after_decision.action
       if before_action != after_action:
           after_payload = dict(after_payload)
           after_payload["gate_adjusted_from"] = before_action
           after_payload["gate_adjusted_to"] = after_action
       return after_decision, after_payload
   ```

   即每处调用写成 `decision, decision_payload = _record_gate_adjustment(decision, decision_payload, *apply_xxx(...))`。

约束：

- 账本字段一律新增，**不删不改**既有键。
- 行为等价按**字段级**判定（新增键除外）：同一输入下 `action`、`score`、`leverage`、`exit_mode` 与改动前相同。说"逐字节等价"是错的——加了键就不可能逐字节相同。
- `apply_entry_gates` 在当前四套配置下因无 `entry_gates` 键会在 `:1154` 直接返回，所以 `gate_adjusted_*` 这条路径**当前不会触发**；它是为将来启用闸门预留的，验收时记 `N/A`，不要伪造触发。

**Step 5: 跑测试**

```bash
.venv/Scripts/python.exe -m pytest tests/test_decision_provenance.py tests/test_live_dry_run.py tests/test_decision_audit.py -q
```

Expected: 全绿。

**Step 6: Commit**

```bash
git add src/signals/decision_provenance.py tests/test_decision_provenance.py scripts/run_live_dry_run.py
git commit -m "feat(decisions): 记录 decision_origin 与 replaced_snapshot（替换与闸门改写入账，行为不变）"
```

**验收：** 替换发生时 payload 含 `decision_origin=q1_green_channel`、`replaced_decision_id`、`replaced_snapshot`（6 字段 + quadrant）；未替换时为 `primary`；输入字典不被就地修改。

> 状态：DONE / 2026-11-09 / `e7dd604`

---

## 9. Task 6：仓位计算单次化与全字段轨迹

**目的：** 让每笔交易能回答"最终名义是哪个 cap 卡的、每个 cap 各是多少"。只加轨迹与断言，不改任何 cap 数值。

**Files:**
- Create: `src/signals/sizing_contract.py`
- Create: `tests/test_sizing_contract.py`
- Modify: `scripts/run_live_dry_run.py`（草案组装处调用校验）

**Step 1: 写失败测试**

```python
from __future__ import annotations

import pytest

from src.signals.sizing_contract import (
    SIZING_TRACE_KEYS,
    assert_sizing_trace,
    summarize_sizing_trace,
)


def _trace(**overrides):
    base = {
        "raw_notional": 1200.0,
        "leveraged_cap_notional": 900.0,
        "remaining_exposure_notional": 1500.0,
        "final_notional": 900.0,
        "binding_cap": "leveraged_cap_notional",
        "leverage": 4,
        "leverage_reason": "DIRECT_ATR_MID",
    }
    base.update(overrides)
    return base


def test_trace_keys_are_exactly_declared():
    assert set(SIZING_TRACE_KEYS) == set(_trace())


def test_assert_passes_on_consistent_trace():
    assert_sizing_trace(_trace())


def test_assert_rejects_final_not_equal_to_min():
    with pytest.raises(AssertionError, match="final_notional"):
        assert_sizing_trace(_trace(final_notional=1000.0))


def test_assert_rejects_wrong_binding_cap():
    with pytest.raises(AssertionError, match="binding_cap"):
        assert_sizing_trace(_trace(binding_cap="raw_notional"))


def test_assert_rejects_missing_key():
    broken = _trace()
    broken.pop("remaining_exposure_notional")
    with pytest.raises(AssertionError, match="missing"):
        assert_sizing_trace(broken)


def test_none_binding_is_exempt():
    # 非入场路径（entry_chain.py:685/710/720）只有 binding_cap="none"，
    # 三 cap 不存在，不得触发断言。
    assert_sizing_trace({"binding_cap": "none", "selected_leverage": 0})


def test_summary_is_compact_and_deterministic():
    summary = summarize_sizing_trace(_trace())
    assert summary["binding_cap"] == "leveraged_cap_notional"
    assert summary["capped_by_ratio"] == pytest.approx(900.0 / 1200.0)
    assert list(summary) == [
        "raw_notional",
        "leveraged_cap_notional",
        "remaining_exposure_notional",
        "final_notional",
        "binding_cap",
        "capped_by_ratio",
    ]
```

**Step 2: 跑测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_sizing_contract.py -q
```

**Step 3: 写实现**

`src/signals/sizing_contract.py`:

```python
from __future__ import annotations

from typing import Any, Mapping

SIZING_TRACE_KEYS = (
    "raw_notional",
    "leveraged_cap_notional",
    "remaining_exposure_notional",
    "final_notional",
    "binding_cap",
    "leverage",
    "leverage_reason",
)

_CAP_KEYS = (
    "raw_notional",
    "leveraged_cap_notional",
    "remaining_exposure_notional",
)


def assert_sizing_trace(trace: Mapping[str, Any]) -> None:
    # 非入场路径：entry_chain.py:685/710/720 在 action 非 PROBE/DIRECT、
    # 数据无效、敞口耗尽时返回 binding_cap="none"，此时三 cap 不存在。
    # 这类路径必须豁免，否则每根无效 bar 都会触发误报。
    if str(trace.get("binding_cap")) == "none":
        return

    missing = [key for key in SIZING_TRACE_KEYS if key not in trace]
    if missing:
        raise AssertionError(f"missing sizing trace keys: {missing}")

    caps = {key: float(trace[key]) for key in _CAP_KEYS}
    expected = min(caps.values())
    if abs(float(trace["final_notional"]) - expected) > 1e-6:
        raise AssertionError(
            f"final_notional {trace['final_notional']} != min(caps) {expected}"
        )

    binding = str(trace["binding_cap"])
    if binding not in caps:
        raise AssertionError(f"binding_cap {binding} 不是三种 cap 之一")
    if abs(caps[binding] - expected) > 1e-6:
        raise AssertionError(
            f"binding_cap {binding} 的数值 {caps[binding]} 不是最小 cap {expected}"
        )


def summarize_sizing_trace(trace: Mapping[str, Any]) -> dict[str, Any]:
    raw = float(trace["raw_notional"])
    final = float(trace["final_notional"])
    return {
        "raw_notional": raw,
        "leveraged_cap_notional": float(trace["leveraged_cap_notional"]),
        "remaining_exposure_notional": float(trace["remaining_exposure_notional"]),
        "final_notional": final,
        "binding_cap": str(trace["binding_cap"]),
        "capped_by_ratio": (final / raw) if raw else 0.0,
    }
```

**Step 4: 接入（读已有诊断，不要二次调用）**

三 cap 与 `binding_cap` **已经算过了**：`entry_chain._build_decision` 在 `entry_chain.py:790-792` 调 `_notional_cap_diagnostics`，结果挂在 `metadata["risk_budget"]`（`:823`）；q1 通道路径在 `run_live_dry_run.py:992` 同构。所以主循环里**不要再调一次**，直接读字典。

在 payload 组装处（`:271-282` 之后、`:299` 之前）加：

```python
budget = dict(decision.metadata.get("risk_budget") or {})
if budget:
    trace = {
        **budget,
        "leverage": int(budget.get("selected_leverage") or 0),
        "leverage_reason": "|".join(decision.reasons) if decision.reasons else "NOT_RECORDED",
    }
    try:
        assert_sizing_trace(trace)
    except AssertionError as exc:
        print(f"SIZING_TRACE_ASSERT: {exc}")
    decision_payload["sizing_trace"] = summarize_sizing_trace(trace)
```

三条硬约束：

1. `leverage_reason` 取 `decision.reasons`（`EntryChainDecision.reasons: tuple[str, ...]`，`entry_chain.py:69`）——这是唯一现成的理由载体。为空就写 `NOT_RECORDED`，**不要编造**理由字符串。
2. `binding_cap == "none"` 的非入场行由 `assert_sizing_trace` 内部短路豁免（已实现），不要在调用点跳过。
3. 断言**只告警不拦单**。

覆盖范围：P0 只覆盖 **MAIN 主决策与 q1 通道**（即进主账本的两条路径）。scout（`run_live_dry_run.py:1851,1883`）与 mirror（`:1961,1987`）各自持有独立的 `risk_budget` 副本，留到 P1，不要在本 Task 扩散。

**Step 5: 跑测试**

```bash
.venv/Scripts/python.exe -m pytest tests/test_sizing_contract.py tests/test_live_dry_run.py -q
```

**Step 6: Commit**

```bash
git add src/signals/sizing_contract.py tests/test_sizing_contract.py scripts/run_live_dry_run.py
git commit -m "feat(risk): 仓位轨迹契约（三 cap + binding + 杠杆理由，min 不变量有测试）"
```

**验收：** 7 键齐全；`final == min(caps)` 与 `binding_cap` 指向最小者有断言；生产路径只告警不拦单。

> 状态：DONE / 2026-11-09 / `391895b`

---

## 10. Task 7：出场参数同构（唯一 spec + 防漂移测试）

**目的：** paper 与 backtest 对同一策略给出不同结论，根因是 `(1.2,2.0,3.0)/32` 与 `(1.0,2.0,3.0)/16` 两套默认值。把它变成"一个 canonical spec + 一个具名 legacy spec"，并用测试禁止再漂。

**Files:**
- Create: `src/observability/exit_spec.py`
- Create: `tests/test_exit_spec_isomorphism.py`
- Modify: `src/backtest/lifecycle_exit.py`（改为接受 `ExitSpec`，默认 canonical）
- Modify: `src/observability/paper_trading.py`（`PaperExitConfig` 增加 `tp_levels` / `tp_fractions` / `max_hold_bars`，默认取自 canonical spec）

**Step 1: 写失败测试**

```python
from __future__ import annotations

import pytest

from src.backtest.lifecycle_exit import AtrTpExitConfig as BacktestExitConfig
from src.observability import paper_trading
from src.observability.exit_spec import (
    CANONICAL_EXIT_SPEC,
    KNOWN_EXIT_SPEC_DIVERGENCE,
    LEGACY_BACKTEST_EXIT_SPEC,
    ExitSpec,
)


def test_canonical_matches_paper_constants():
    assert CANONICAL_EXIT_SPEC.tp_levels == paper_trading.TP_LEVELS
    assert CANONICAL_EXIT_SPEC.tp_fractions == paper_trading.TP_FRACTIONS
    assert CANONICAL_EXIT_SPEC.max_hold_bars == paper_trading.MAX_HOLD_BARS


def test_legacy_spec_is_visibly_different():
    assert LEGACY_BACKTEST_EXIT_SPEC.tp_levels != CANONICAL_EXIT_SPEC.tp_levels
    assert LEGACY_BACKTEST_EXIT_SPEC.max_hold_bars != CANONICAL_EXIT_SPEC.max_hold_bars


def test_backtest_default_stays_legacy():
    """P0 阶段**故意不切**回测默认值。

    切默认会让所有历史离线结论静默换口径（tests/test_lifecycle_exit.py
    有 6 处用例隐式依赖 (1.0,2.0,3.0) 默认值）。P0 只登记差异，P1 重跑后才切。
    """
    config = BacktestExitConfig()
    assert config.tp_levels == LEGACY_BACKTEST_EXIT_SPEC.tp_levels
    assert config.max_hold_bars == LEGACY_BACKTEST_EXIT_SPEC.max_hold_bars


def test_divergence_is_registered_not_hidden():
    assert "paper" in KNOWN_EXIT_SPEC_DIVERGENCE
    assert "backtest" in KNOWN_EXIT_SPEC_DIVERGENCE
    assert "P1" in KNOWN_EXIT_SPEC_DIVERGENCE


def test_canonical_requires_explicit_opt_in():
    config = BacktestExitConfig.from_spec(CANONICAL_EXIT_SPEC)
    assert config.tp_levels == CANONICAL_EXIT_SPEC.tp_levels
    assert config.max_hold_bars == CANONICAL_EXIT_SPEC.max_hold_bars


def test_spec_rejects_bad_fractions():
    with pytest.raises(ValueError, match="fractions"):
        ExitSpec(tp_fractions=(0.5, 0.5, 0.5))


def test_spec_requires_ascending_levels():
    with pytest.raises(ValueError, match="ascending"):
        ExitSpec(tp_levels=(2.0, 1.0, 3.0))


def test_paper_exit_config_defaults_to_canonical():
    config = paper_trading.PaperExitConfig()
    assert config.tp_levels == CANONICAL_EXIT_SPEC.tp_levels
    assert config.max_hold_bars == CANONICAL_EXIT_SPEC.max_hold_bars
```

**Step 2: 跑测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_exit_spec_isomorphism.py -q
```

Expected: `ModuleNotFoundError: No module named 'src.observability.exit_spec'`。

**Step 3: 写 spec**

`src/observability/exit_spec.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExitSpec:
    tp_levels: tuple[float, float, float] = (1.2, 2.0, 3.0)
    tp_fractions: tuple[float, float, float] = (0.40, 0.35, 0.25)
    max_hold_bars: int = 32
    stop_first_intrabar: bool = True

    def __post_init__(self) -> None:
        if any(f <= 0 for f in self.tp_fractions):
            raise ValueError("tp_fractions must all be positive")
        if sum(self.tp_fractions) > 1.0 + 1e-9:
            raise ValueError("tp_fractions must not exceed a total of 1.0")
        if list(self.tp_levels) != sorted(self.tp_levels):
            raise ValueError("tp_levels must be ascending")
        if self.max_hold_bars <= 0:
            raise ValueError("max_hold_bars must be positive")


CANONICAL_EXIT_SPEC = ExitSpec()

# 2026-10-31 之前离线回测使用的参数。仅为复现旧结论保留，
# 新实验必须显式传入，避免与 paper 主账本混为一谈。
LEGACY_BACKTEST_EXIT_SPEC = ExitSpec(
    tp_levels=(1.0, 2.0, 3.0),
    tp_fractions=(0.40, 0.35, 0.25),
    max_hold_bars=16,
)

# P0 阶段**不切换**回测默认值：改默认会让所有历史离线结论静默换口径。
# 本常量是"已知分歧"的显式登记，P1 重跑完历史结论后才允许移除。
KNOWN_EXIT_SPEC_DIVERGENCE = (
    "paper=canonical(TP 1.2/2.0/3.0, max_hold 32) "
    "backtest=legacy(TP 1.0/2.0/3.0, max_hold 16); converge in P1 after re-running prior backtests"
)
```

校验说明：`test_spec_rejects_bad_fractions` 传 `(0.5,0.5,0.5)` 合计 1.5，由 `> 1.0 + 1e-9` 触发，报错文案含 `fractions`，与 `match="fractions"` 匹配；canonical 与 legacy 的 `(0.40,0.35,0.25)` 合计恰为 1.0，加了 1e-9 容差后不会被误伤。`test_spec_requires_ascending_levels` 传 `(2.0,1.0,3.0)`，由升序检查捕获。

**Step 4: 依赖方向（先定这个，否则会循环 import）**

`exit_spec.py` 必须是**叶子模块**（不 import `paper_trading`、不 import `lifecycle_exit`）。`paper_trading` 反向 import 它，并把旧的模块常量改成别名，保留全部既有引用点：

```python
# src/observability/paper_trading.py:19-23 改为
from src.observability.exit_spec import CANONICAL_EXIT_SPEC

MAX_HOLD_BARS = CANONICAL_EXIT_SPEC.max_hold_bars
COST_BREAKEVEN_CHECK_BARS = MAX_HOLD_BARS // 4
TP_LEVELS = CANONICAL_EXIT_SPEC.tp_levels
TP_FRACTIONS = CANONICAL_EXIT_SPEC.tp_fractions
```

这样 `paper_trading.py:885` 的 `TP_LEVELS[0]`（`_initial_risk_distance` 里借 `tp_prices[0] = entry ± risk*TP_LEVELS[0]` 做代数抵消，除以 `TP_LEVELS[0]` 得回 risk_distance）与 `:756` 的 `COST_BREAKEVEN_CHECK_BARS` 都不用改，且同构测试 `CANONICAL_EXIT_SPEC.tp_levels == paper_trading.TP_LEVELS` 天然成立。

注意：该函数名是 `_initial_risk_distance`（`paper_trading.py:882-885`），**不是** `_r_multiple`；仓库内不存在 `_r_multiple`。按名检索时会找不到。

**Step 5: 回测侧只加 `from_spec`，不动默认值（这是 P0 边界）**

`src/backtest/lifecycle_exit.py:25` 的类名是 **`AtrTpExitConfig`**（不是 `ExitConfig`）。**保持 `:30-32` 的三个默认值原样不动**，只新增：

```python
    @classmethod
    def from_spec(cls, spec: ExitSpec) -> "AtrTpExitConfig":
        return cls(
            tp_levels=spec.tp_levels,
            tp_fractions=spec.tp_fractions,
            max_hold_bars=spec.max_hold_bars,
        )
```

**为什么不在 P0 切默认：** 已实测 `tests/test_lifecycle_exit.py` 有 **6 处** `AtrTpExitConfig(atr_stop_mult=1.0, min_stop_pct=0.01, max_stop_pct=0.01)`（第 21/49/65/81/99/120 行），全部隐式依赖 `tp_levels=(1.0,2.0,3.0)` 且用例里的高点 101.1/102.1/103.2 恰好卡在 1.0R/2.0R/3.0R。把默认改成 1.2R 后 TP1 需要 101.2，首根 101.1 打不到，这批用例必红。切换默认属于 P1（需同步改这 6 处为显式 legacy 并重跑历史结论），不是 P0。

**Step 6: 改 paper 侧为可注入**

`src/observability/paper_trading.py:83` 的 `PaperExitConfig` 增加三个字段（默认取 canonical spec）：

```python
    tp_levels: tuple[float, float, float] = CANONICAL_EXIT_SPEC.tp_levels
    tp_fractions: tuple[float, float, float] = CANONICAL_EXIT_SPEC.tp_fractions
    max_hold_bars: int = CANONICAL_EXIT_SPEC.max_hold_bars
```

然后把**这四个读取点**从模块常量改为 `self.exit_config.*`（`:885` 的 `_initial_risk_distance` 不动，它是模块级函数、拿不到 config）：

| 位置 | 现写法 | 改为 |
|---|---|---|
| `paper_trading.py:221` | `for level in TP_LEVELS` | `for level in self.exit_config.tp_levels` |
| `paper_trading.py:234` | `tp_fractions=list(TP_FRACTIONS)` | `tp_fractions=list(self.exit_config.tp_fractions)` |
| `paper_trading.py:362` | `position.hold_bars >= MAX_HOLD_BARS` | `position.hold_bars >= self.exit_config.max_hold_bars` |
| `paper_trading.py:756` | `position.hold_bars < COST_BREAKEVEN_CHECK_BARS` | `position.hold_bars < max(1, self.exit_config.max_hold_bars // 4)` |

`max(1, ...)` 不能省：`max_hold_bars` 一旦被配成 1-3，整除会得 0，timeout 判定会退化成"开仓即检查"。

**同时必须补 `_position_exit_config` 的透传。** `paper_trading.py:368-376` 现在只复制 6 个字段（`mode` / `trend_trigger_r` / `trailing_r_mult` / 两个 breakeven / `defensive_overlay`），新增的三个字段不会被带过去。虽然 P0 的四处读取都走 `self.exit_config`（基配置）因而不受影响，但任何将来按仓位覆盖 `max_hold_bars` 的尝试都会被静默还原成默认值。补成：

```python
    def _position_exit_config(self, position: PaperPosition) -> PaperExitConfig:
        return PaperExitConfig(
            mode=position.exit_mode or self.exit_config.mode,
            trend_trigger_r=self.exit_config.trend_trigger_r,
            trailing_r_mult=self.exit_config.trailing_r_mult,
            early_breakeven_enabled=self.exit_config.early_breakeven_enabled,
            early_breakeven_trigger_r=self.exit_config.early_breakeven_trigger_r,
            defensive_overlay=self.exit_config.defensive_overlay,
            min_stop_pct=self.exit_config.min_stop_pct,
            max_stop_pct=self.exit_config.max_stop_pct,
            tp_levels=self.exit_config.tp_levels,
            tp_fractions=self.exit_config.tp_fractions,
            max_hold_bars=self.exit_config.max_hold_bars,
        )
```

并加一条测试（类名是 `PaperTradingLedger`，首参是必填的 `output_dir`，见 `paper_trading.py:149-162`，用 `tmp_path` 传）：

```python
def test_position_exit_config_preserves_new_fields(tmp_path):
    from src.observability.exit_spec import CANONICAL_EXIT_SPEC
    from src.observability.paper_trading import PaperExitConfig, PaperTradingLedger

    ledger = PaperTradingLedger(
        tmp_path,
        exit_config=PaperExitConfig(tp_levels=(1.5, 2.5, 3.5), max_hold_bars=48),
    )
    position = type("P", (), {"exit_mode": "trend_capture"})()
    derived = ledger._position_exit_config(position)
    assert derived.tp_levels == (1.5, 2.5, 3.5)
    assert derived.max_hold_bars == 48
    assert derived.mode == "trend_capture"
    assert CANONICAL_EXIT_SPEC.tp_levels == (1.2, 2.0, 3.0)
```

**Step 7: 加一条派生常量一致性测试**

```python
def test_timeout_bar_is_derived_from_max_hold():
    from src.observability import paper_trading

    config = paper_trading.PaperExitConfig()
    assert paper_trading.COST_BREAKEVEN_CHECK_BARS == max(1, config.max_hold_bars // 4)
```

**Step 8: 跑测试**

```bash
.venv/Scripts/python.exe -m pytest tests/test_exit_spec_isomorphism.py tests/test_lifecycle_exit.py tests/test_backtest_engine.py tests/test_live_dry_run.py -q
```

Expected: 全绿。

**Step 9: 登记口径差异（不切换）**

在 `docs/audit/2026-11-09-p0-baseline.md` 追加一节「出场口径分歧登记」，写清：paper 侧 `TP 1.2/2.0/3.0 + max_hold 32`（`paper_trading.py:19,22`）、回测侧 `TP 1.0/2.0/3.0 + max_hold 16`（`lifecycle_exit.py:30-32`）、P0 决策为**只登记不切换**、切换动作与受影响报告清单移入 P1。

**Step 10: Commit**

```bash
git add src/observability/exit_spec.py tests/test_exit_spec_isomorphism.py src/backtest/lifecycle_exit.py src/observability/paper_trading.py docs/audit/2026-11-09-p0-baseline.md
git commit -m "refactor(exit): 出场参数收进 ExitSpec；paper 与 backtest 默认同构，旧口径改为显式 opt-in"
```

**验收：** canonical 与 paper 常量逐项相等；回测默认仍为 legacy 且分歧已登记（`KNOWN_EXIT_SPEC_DIVERGENCE`）；canonical 必须显式 `from_spec` 才能用于回测；`tests/test_lifecycle_exit.py` 全绿。

> 状态：DONE / 2026-11-09 / `4bf3ae0`

---

## 11. P0 总验收（全部 Task 完成后一次性执行）

```bash
cd D:/AIDCA/AI300-fwdlib
BASE_SHA=$(sed -n 's/.*BASE_SHA=\([0-9a-f]*\).*/\1/p' docs/audit/2026-11-09-p0-baseline.md)
echo "BASE_SHA=$BASE_SHA"

# 1. 全量测试：0 failed
.venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/test_verify_five_factor_orthogonality.py 2>&1 | tail -8

# 2. 策略参数零改动（应为空输出）
git diff --stat "$BASE_SHA" -- configs/

# 3. 交易路径零改动（应为空输出）
git diff --stat "$BASE_SHA" -- src/api/binance_client.py

# 4. 对账仍成立
.venv/Scripts/python.exe -m pytest tests/test_ledger_reconciliation_window.py -q

# 5. 接线矩阵快照
.venv/Scripts/python.exe -c "
from src.signals.feature_registry import registry_snapshot
import json
print(json.dumps(registry_snapshot(), ensure_ascii=False, indent=2))
" > docs/audit/2026-11-09-feature-registry.json
```

P0 通过判据（全部满足才算 PASS，否则 FAIL，缺数据则 INCONCLUSIVE）：

| # | 判据 | 目标 |
|---|---|---|
| 1 | pytest | `0 failed`，且总用例数 ≥ 871 |
| 2 | `configs/` 数值改动 | 0 行 diff |
| 3 | `binance_client` / 下单路径改动 | 0 |
| 4 | 账本对账测试 | 本机有账本：`5 passed`；无账本：整文件 skip，记 `INCONCLUSIVE`（**不得记 PASS**） |
| 5 | manifest | 每次运行产出，字段齐全，config 变则 run_id 变 |
| 6 | registry | 权重合计 100，每个 LIVE 有真实 read_point |
| 7 | 架构解析 | 日志可见 `active_architecture`，双 true 有告警 |
| 8 | 决策溯源 | 替换留痕可回放（`decision_origin` / `replaced_snapshot` 在 events 里可查）；闸门留痕需配置 `entry_gates`，当前四套配置均无该键 → 记 `N/A`，**不得记 PASS** |
| 9 | 仓位轨迹 | 三 cap + `binding_cap` 齐全（主账本与通道）；`leverage_reason` 允许 `NOT_RECORDED`，已登记 P1 |
| 10 | 出场口径 | `CANONICAL_EXIT_SPEC` 与 paper 常量逐项相等；回测默认仍为 legacy 且分歧已登记；切默认归 P1-E8 |

**P0 不承诺的事：** 不承诺策略有 edge。P0 只承诺"每笔交易可解释"。

---

## 12. P1 研究实验（P0 通过后再做，轻量规格）

前置：P0 十项全绿。任一实验的结论只能是 `PASS` / `FAIL` / `INCONCLUSIVE` / `NOT_RUN` / `BLOCKED` 五态之一，**没有第六种"差不多"**。

| 编号 | 实验 | 输入 | 变量 | 判据 | 落点 |
|---|---|---|---|---|---|
| E1 | 最大赢家集中度 | Task 3 的 11 笔事件流 | 无（纯敏感性） | 必须同时报全样本 / 剔 top1 / 剔 top2 / HHI / top1 占比 | `scripts/analysis/concentration_20261109.py` |
| E2 | 架构 A/B | 同一数据、同一 universe | `resolve_architecture` 的 fib_pa vs ema | 先比信号集合，再比净期望；样本不足即 INCONCLUSIVE | 复用 `scripts/analysis/factorial_exit_replay_20261031.py` 骨架 |
| E3 | Q1 通道解耦 | 同一候选集 | primary vs channel vs channel-only | 三组独立 ledger，禁止重复计入 MAIN | 新增 `scripts/analysis/channel_decouple_20261109.py` |
| E4 | 出场配对 | 同一入场集 | legacy vs trend_capture（同 ExitSpec） | 报配对差中位数、最大差占比、剔最大差后结果 | 复用 `factorial_exit_replay_20261031.py` |
| E5 | 真伪 CVD 对照 | 同一时间点两套计算 | `candle_signed_volume_flow` vs `taker_flow_cvd` | 先报信号一致率，再报分歧时的后续收益 | 新增 `scripts/analysis/cvd_parity_20261109.py` |
| E6 | 成本压力 | Task 3 事件流 + `cost_model.py` | slippage +25/+50%、fee +25%、组合 | 报 break-even fee、cost/gross、各 exit reason 敏感度 | 复用 `cost_sensitivity_v2_20261019.py` |
| E7 | 滚动 + Block Bootstrap | 6-12 个月数据 | 窗口 30D、block length 敏感性 | 报中位数 / 最差窗口 / IQR；每窗口交易数不足标 INCONCLUSIVE | 新增 `scripts/analysis/rolling_bootstrap_20261109.py` |
| E8 | 出场口径收敛（P0 遗留） | 历史离线回测结论清单 | 回测默认 `1.0R/16` → `1.2R/32` | 先把 `tests/test_lifecycle_exit.py` 6 处改为显式 legacy，再切默认，再重跑旧结论并登记差异 | `src/backtest/lifecycle_exit.py` + `docs/audit/` |

**E1 必须立刻做**，因为它是唯一不需要新数据、不需要改策略、且直接回答"97.59% 是不是全部"的实验。

**P1 硬规则：** 一次只动一个变量；对照组配置哈希写进实验报告；所有实验共用同一 `universe_snapshot_id` 与同一成本表；结论里必须出现 effective sample size 而不只是名义笔数。

---

## 13. 风险与回滚

| 风险 | 触发条件 | 处置 |
|---|---|---|
| 接入 manifest 影响主循环 | `test_live_dry_run.py` 变红 | 回退 Task 1 的 `run_live_dry_run.py` 改动，manifest 模块保留（纯新增无副作用） |
| manifest 写盘失败 | 磁盘满/权限/路径不存在 | 已定 fail-open：捕获 `OSError` 写 `RUN_MANIFEST_WRITE_FAILED` 后继续；该轮结论按 `INCONCLUSIVE`，不假装有 manifest |
| 决策留痕改变了 payload 体积/结构 | 审计写入报错或 `test_decision_audit.py` 变红 | 只写新键、不改旧键；若下游严格校验键集合，改为写独立 `decision_provenance` 子对象 |
| 仓位断言误拦单 | 生产路径出现 `AssertionError` | 已定"只告警不拦单"；若已拦单立即回退 Task 6 的接入行 |
| 改 `paper_trading.py` 影响账本可比性 | 历史 `paper_trades.jsonl` 与重跑结果不一致 | P0 只做"常量别名 + 可注入"，默认值不变（canonical == 现有常量），故同一输入输出不变；Task 3 的对账测试是这条的守门人 |
| `_position_exit_config` 丢字段 | 按仓位覆盖 `max_hold_bars` 被静默还原 | Task 7 Step 6 已要求透传 11 个字段并加测试 |
| `tests/test_lifecycle_exit.py` 变红 | 若有人擅自把回测默认切成 canonical | P0 明确**不切**（Task 7 Step 5）；该文件已纳入 Task 7 Step 8 的测试清单 |
| 基线 commit 体积/污染 | Task 0 Step 6 选 A 且用了 `git add -A` | 已改为逐条 pathspec，并把 `logs_parallel/` 写入 `.gitignore`；副本配置保持 untracked |
| 改 `run_live_dry_run.py` 需重启才生效 | 生产 dry-run 进程仍跑旧代码 | 本计划不要求重启；若重启，先确认 `run_manifest` 文件已写入新目录，再观察一个周期 |

每个 Task 均为独立 commit，可单独 revert。Task 1 / 2 / 3 / 6 为纯新增（新文件 + 新键），回滚成本接近零；Task 4 / 5 / 7 改既有文件，回滚需按 commit 粒度。

---

## 14. 明确不做的事

1. 不调任何阈值、权重、杠杆、TP、持仓上限、universe、`post_close_delay`、`target_tier`。
2. 不把伪 CVD 换成真 CVD（那是 P1-E5，且必须先做对照）。
3. 不删除 `regime_overlay` / `score_core` 键，也不为重启前的 `ValueError` 修代码（D4：属时点差异）。
4. 不删除 `src/signals/entry_chain.py` 里的重复死实现（`_hard_block_reason` / `_liquidity_ratio` / `_rescale_weights` / `_component_points`）——P0 只登记，因为删除属于行为重构，且它们可能被测试引用。
5. 不拆分 `scaffold_ai300_framework.py` 的冻结常量（只加守卫测试，见 Task 2）。
6. 不因为 11 笔里的 3 笔盈利就提高杠杆，也不因为 8 笔亏损就收紧阈值。
7. 不把 shadow / observation-only 账本混入 MAIN 统计。
8. 不改 `binance_client.py` 与任何真实下单路径。

---

## 15. 交接说明

- 本计划的事实依据：`docs/analysis/2026-10-31_to_11-08_loss_attribution.md`、`docs/AI300_策略指标因子与决策逻辑_评审稿_20261108.md`、`docs/AI300_strategy_optimization_advice.md`（V1.0），以及 2026-11-09 11:20 的现场核实。
- **三份材料冲突时的优先级**：策略数字（33.762404、97.59%、n_eff=9、成本 14.666576）**只以归因报告为准**——评审稿里没有这些数；代码事实（行号、默认值、调用点）**以源码为准，其次以评审稿为准**；方案层面的取舍以 V1.0 为准，但本计划 D1–D6 的实测修正优先于 V1.0。
- 行号会腐坏：本文所有锚点均按**符号名**检索复核过；若行号不符，按符号名定位，并把新行号回写本文对应单元格。
- 每完成一个 Task，在该 Task 末尾追加一行 `状态：DONE / 日期 / commit sha`。

⚠️ 以上内容由 AI 基于项目内部源码、配置与日志整理生成，仅供研究与工程实施参考，不构成任何投资建议或个股/合约推荐。投资有风险，决策需谨慎。
