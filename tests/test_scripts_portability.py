"""锁住分析脚本在 VPS 上可跑：只用标准库，且 CLI 帮助能正常退出。

VPS 解释器是 conda python 3.12，没有仓库 venv；脚本一旦 import numpy/pandas/requests
就会在生产机上直接崩。这里用 AST 静态检查 import，不执行被测模块。
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_REVIEW = REPO_ROOT / "scripts" / "report_strategy_review.py"
AUDIT_WIRING = REPO_ROOT / "scripts" / "audit_config_wiring.py"
SCRIPTS = [REPORT_REVIEW, AUDIT_WIRING]
PROJECT_INTERNAL = {"src"}


def _top_level_imports(path: Path) -> set[str]:
    """收集所有 import / from ... import 的顶层模块名（含函数内延迟导入）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue  # 显式相对导入不涉及第三方包
            if node.module:
                modules.add(node.module.split(".")[0])
    return modules


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_only_stdlib_or_project_imports(path: Path) -> None:
    allowed = set(sys.stdlib_module_names) | PROJECT_INTERNAL
    offenders = sorted(_top_level_imports(path) - allowed)
    assert offenders == [], f"{path.name} 引入了非标准库依赖: {offenders}"


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_help_exits_zero(path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(path), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "usage" in completed.stdout.lower()


def test_report_review_exposes_logs_root() -> None:
    assert "--logs-root" in REPORT_REVIEW.read_text(encoding="utf-8")


def test_audit_wiring_exposes_configs_dir() -> None:
    assert "--configs-dir" in AUDIT_WIRING.read_text(encoding="utf-8")
