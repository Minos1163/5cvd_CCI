"""运行事实单一来源：每次 dry-run / 回测启动即落盘一份不可变 manifest。

设计约束（P0）：
- **只写文件，不参与任何判定**。manifest 缺失时本轮结论按 INCONCLUSIVE，而不是假装有。
- 文件名带 ``run_id``（含启动时间与配置哈希），同一天换配置重启不会撞上
  "同路径不同哈希"的拒绝写入。
- ``config_sha256`` 是内容哈希，不是 mtime：同一份配置在不同机器/不同时间读出同一个值。
"""

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
    """返回 commit / branch / 工作树是否脏。

    三者都可能是 ``None``：git 不可用、非仓库、或命令失败时不做猜测。
    ``working_tree_dirty`` 用 ``None`` 而不是 ``False`` 表达"没测出来"，
    避免把"未知"记成"干净"。
    """
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
        """落盘。同路径已存在且 config 哈希不同时**拒绝覆盖**——那是真错，不是竞态。

        正常路径下文件名带 ``run_id``，不会走到 raise。
        """
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
