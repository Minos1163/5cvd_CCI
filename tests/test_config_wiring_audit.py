"""scripts/audit_config_wiring.py 的核心纯函数测试。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_config_wiring.py"
_spec = importlib.util.spec_from_file_location("audit_config_wiring", _SCRIPT)
assert _spec is not None and _spec.loader is not None
acw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(acw)


DATACLASS_SOURCE = '''
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EntryChainConfig:
    plain: float = 1.0
    annotated_only: int
    with_factory: tuple[str, ...] = field(default_factory=tuple)
    shadowed: bool = False
'''


def test_extract_fields_reads_annassign_only() -> None:
    fields = acw.extract_fields(DATACLASS_SOURCE)
    assert fields == ["plain", "annotated_only", "with_factory", "shadowed"]


def test_extract_fields_uses_given_class_name() -> None:
    source = '''
from dataclasses import dataclass


@dataclass
class Other:
    a: int = 0


@dataclass
class EntryChainConfig:
    b: int = 0
'''
    assert acw.extract_fields(source, "Other") == ["a"]
    assert acw.extract_fields(source) == ["b"]


def test_extract_fields_missing_class_raises() -> None:
    with pytest.raises(ValueError):
        acw.extract_fields("x = 1\n")


def test_attribute_read_is_live_read() -> None:
    reader = "def f(cfg):\n    return cfg.plain\n"
    result = acw.classify({"src/a.py": reader}, ["plain", "shadowed"])
    assert result["plain"]["status"] == acw.LIVE_READ
    assert result["plain"]["read_count"] == 1
    assert result["plain"]["locations"] == ["src/a.py:2"]
    assert result["shadowed"]["status"] == acw.DECLARED_ONLY


def test_self_config_and_suffixed_holders_are_live_read() -> None:
    reader = (
        "def f(self, config, entry_cfg):\n"
        "    a = self.config.plain\n"
        "    b = entry_cfg.with_factory\n"
        "    c = config.annotated_only\n"
    )
    result = acw.classify(
        {"src/a.py": reader},
        ["plain", "with_factory", "annotated_only"],
    )
    assert all(row["status"] == acw.LIVE_READ for row in result.values())


def test_dict_get_and_subscript_are_live_read() -> None:
    reader = (
        "def f(payload, cfg):\n"
        "    a = payload.get('plain')\n"
        "    b = payload['with_factory']\n"
    )
    result = acw.classify({"src/a.py": reader}, ["plain", "with_factory", "shadowed"])
    assert result["plain"]["status"] == acw.LIVE_READ
    assert result["with_factory"]["status"] == acw.LIVE_READ
    assert result["shadowed"]["status"] == acw.DECLARED_ONLY


def test_comments_and_strings_are_not_reads() -> None:
    reader = (
        "# cfg.plain is documented here\n"
        'NOTE = "cfg.annotated_only"\n'
        "def f(cfg):\n"
        "    return 1\n"
    )
    result = acw.classify({"src/a.py": reader}, ["plain", "annotated_only"])
    assert result["plain"]["status"] == acw.DECLARED_ONLY
    assert result["annotated_only"]["status"] == acw.DECLARED_ONLY


def test_non_config_holder_is_not_a_read() -> None:
    reader = "def f(state):\n    return state.plain\n"
    result = acw.classify({"src/a.py": reader}, ["plain"])
    assert result["plain"]["status"] == acw.DECLARED_ONLY


def test_many_locations_are_capped() -> None:
    lines = ["def f(cfg):"] + ["    x = cfg.plain"] * 8
    result = acw.classify({"src/a.py": "\n".join(lines)}, ["plain"])
    assert result["plain"]["read_count"] == 8
    assert len(result["plain"]["locations"]) == acw.MAX_LOCATIONS


def test_excluded_file_is_ignored() -> None:
    reader = "def f(cfg):\n    return cfg.plain\n"
    result = acw.classify(
        {"src/signals/entry_chain_config.py": reader},
        ["plain"],
        exclude=["src/signals/entry_chain_config.py"],
    )
    assert result["plain"]["status"] == acw.DECLARED_ONLY


def test_unknown_keys_detected() -> None:
    payloads = {
        "entry_chain.a.json": {"plain": 1, "typo_key": 2},
        "entry_chain.b.json": {"plain": 1, "another_typo": 3},
    }
    unknown = acw.find_unknown_keys(payloads, ["plain"])
    assert unknown == {
        "another_typo": ["entry_chain.b.json"],
        "typo_key": ["entry_chain.a.json"],
    }


def test_unknown_keys_empty_when_all_declared() -> None:
    assert acw.find_unknown_keys({"entry_chain.a.json": {"plain": 1}}, ["plain"]) == {}


def test_classify_is_deterministic_and_sorted() -> None:
    sources = {
        "src/b.py": "def f(cfg):\n    return cfg.plain\n",
        "src/a.py": "def g(cfg):\n    return cfg.plain\n",
    }
    result = acw.classify(sources, ["plain"])
    assert result["plain"]["locations"] == ["src/a.py:2", "src/b.py:2"]
    again = acw.classify(sources, ["plain"])
    assert result == again


def test_getattr_is_dynamic_read_not_declared_only() -> None:
    """getattr 命中要单独归类，不能混进 LIVE_READ，也不能落到 DECLARED_ONLY。

    这是本工具可用性的关键：把"运行时才可能读"报成"确定没读"，
    会让人去删一个其实在用的开关。
    """
    reader = (
        "def f(cfg):\n"
        "    return bool(getattr(cfg, 'risk_first_sizing_enabled', False))\n"
    )
    result = acw.classify({"src/a.py": reader}, ["risk_first_sizing_enabled"])
    row = result["risk_first_sizing_enabled"]
    assert row["status"] == acw.DYNAMIC_READ
    assert "getattr" in row["via"]


def test_direct_and_dynamic_hits_keep_both_evidences() -> None:
    reader = (
        "def f(cfg):\n"
        "    a = cfg.entry_gates\n"
        "    b = getattr(cfg, 'entry_gates', ())\n"
    )
    row = acw.classify({"src/a.py": reader}, ["entry_gates"])["entry_gates"]
    assert row["status"] == acw.LIVE_READ, "有直接读取时以 LIVE_READ 为准"
    vias = {item["via"] for item in row["dynamic_evidence"]}
    assert "getattr" in vias, "动态路径的证据不能被直接读取覆盖掉"


def test_vars_get_is_dynamic_read() -> None:
    reader = (
        "def f(cfg):\n"
        "    return vars(cfg).get('probe_fraction')\n"
    )
    row = acw.classify({"src/a.py": reader}, ["probe_fraction"])["probe_fraction"]
    assert row["status"] == acw.DYNAMIC_READ
    assert row["via"] == ["vars"]
