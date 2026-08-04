# -*- coding: utf-8 -*-
"""audit_duplicate_json_keys.py 的单元测试。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_duplicate_json_keys import scan_file  # noqa: E402


def test_same_object_duplicate_detected(tmp_path: Path):
    p = tmp_path / "dup.json"
    p.write_text('{"a": 1, "a": 2, "b": 3}', encoding="utf-8")
    dup, cross = scan_file(p)
    assert dup == ["a (x2)"]
    assert "a (x2)" in cross


def test_cross_object_same_name_is_not_duplicate(tmp_path: Path):
    # 主配置的真实场景: probe_conditions.long_threshold_offset 与顶层 long_threshold_offset
    p = tmp_path / "nested.json"
    p.write_text(
        '{"long_threshold_offset": 10.0, "probe_conditions": {"long_threshold_offset": 7.0}}',
        encoding="utf-8",
    )
    dup, cross = scan_file(p)
    assert dup == []  # 同一对象内无重复 → 不视为错误
    assert "long_threshold_offset (x2)" in cross  # 仅 info 提示


def test_clean_file(tmp_path: Path):
    p = tmp_path / "clean.json"
    p.write_text('{"a": 1, "b": {"c": 2}}', encoding="utf-8")
    dup, cross = scan_file(p)
    assert dup == []
    assert cross == []
