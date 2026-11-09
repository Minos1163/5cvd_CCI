"""锁住生产部署口径（2026-11-09 收敛为单一 systemd 单元后）。

背景：仓库里曾有三份互相矛盾的 unit，且没有一份与 VPS 实跑一致。这些断言的目的
不是"描述现状"，而是**防止回潮**：任何人把解释器改回 .venv、把 config 改回
highest_win、或重新引入影子实例，都会在这里失败。
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_DIR = REPO_ROOT / "deploy"
SYSTEMD_DIR = DEPLOY_DIR / "systemd"
DRY_RUN_UNIT = SYSTEMD_DIR / "ai300-dry-run.service"
VPS_OPS = REPO_ROOT / "scripts" / "vps_ops.sh"

EXEC_START_PREFIX = "ExecStart="


def _exec_start() -> str:
    """返回 ExecStart 的值（不含前缀）。注释里提到旧口径不影响本判据。"""
    text = DRY_RUN_UNIT.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith(EXEC_START_PREFIX):
            return line[len(EXEC_START_PREFIX) :]
    raise AssertionError(f"{DRY_RUN_UNIT} 缺少 ExecStart 行")


def test_dry_run_unit_exists_at_expected_path() -> None:
    assert DRY_RUN_UNIT.is_file(), "生产单元必须存在，否则 install-unit 无从拷贝"


def test_dry_run_unit_working_directory() -> None:
    lines = []
    for line in DRY_RUN_UNIT.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("WorkingDirectory"):
            lines.append(stripped)
    assert lines == ["WorkingDirectory=/root/AIBOT"]


@pytest.mark.parametrize(
    "expected",
    [
        "/root/anaconda3/bin/python",
        "configs/entry_chain.dry_run_regime_shadow.json",
        "--post-close-delay-seconds 10",
        "--align-to-kline-close",
        "--log-root /root/AIBOT/logs",
    ],
)
def test_exec_start_matches_vps_reality(expected: str) -> None:
    assert expected in _exec_start()


@pytest.mark.parametrize(
    "forbidden",
    [
        ".venv/bin/python",
        "highest_win",
        "--target-tier aggressive",
        "--post-close-delay-seconds 5",
    ],
)
def test_exec_start_has_no_stale_invocation(forbidden: str) -> None:
    assert forbidden not in _exec_start(), f"ExecStart 仍带旧口径: {forbidden}"


def test_deploy_tree_has_no_dead_shadow_path() -> None:
    """影子目录已改名，任何 deploy/ 下的文本都不该再指向它。"""
    offenders = []
    for path in sorted(DEPLOY_DIR.rglob("*")):
        if not path.is_file():
            continue
        if "AIBOT-shadow" in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == [], f"deploy/ 下仍有指向已删除目录的引用: {offenders}"


@pytest.mark.parametrize("name", ["aibot.service", "ai300-shadow-regime.service"])
def test_duplicate_and_dead_units_removed(name: str) -> None:
    assert not (SYSTEMD_DIR / name).exists(), f"{name} 已废弃，保留只会误导部署"


def test_vps_ops_script_exists_and_has_no_dead_shadow_path() -> None:
    assert VPS_OPS.is_file()
    assert "AIBOT-shadow" not in VPS_OPS.read_text(encoding="utf-8", errors="ignore")
