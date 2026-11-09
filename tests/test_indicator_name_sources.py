from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.indicators.indicator_spec import INDICATOR_NAMES

ROOT = Path(__file__).resolve().parents[1]

# 03 期冻结契约与当前 canonical 规格的唯一允许差异。
# 新增差异必须先改这里，再改实现——防止名源再次静默分叉。
#
# 背景（2026-11-09 核实）：`scripts/scaffold_ai300_framework.py` 里有一份
# **生成 `src/indicators/indicator_spec.py` 的模板**（模板键就在 :2074），
# 模板仍写 RSI，而实际文件已被手工改成 EMA。也就是说：
#   1) 重跑 scaffold 会把 canonical 覆盖回 RSI；
#   2) 该常量不在模块顶层（在模板字符串内），`from scripts.scaffold... import`
#      根本拿不到，且 ast 遍历找不到模块级 Assign。
# 故只能用"按行首锚定的正则"读取，并把差异显式登记在这里。
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
