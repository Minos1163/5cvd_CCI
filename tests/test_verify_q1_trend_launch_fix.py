# -*- coding: utf-8 -*-
"""verify_q1_trend_launch_fix.py 的路径解析修复单测。

背景:VPS 上从任意目录运行(未 cd /root/AIBOT)时,--config/--log-root
按 CWD 解析会 FileNotFoundError。_resolve_path 应:绝对路径原样、
相对路径优先 CWD、CWD 不存在时回退项目根。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_q1_trend_launch_fix import _PROJECT_ROOT, _resolve_path  # noqa: E402


def test_resolve_path_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "x.json"
    assert _resolve_path(str(target)) == target


def test_resolve_path_cwd_priority(tmp_path, monkeypatch):
    (tmp_path / "logs").mkdir()
    monkeypatch.chdir(tmp_path)
    p = _resolve_path("logs")
    assert p == Path("logs")  # CWD 下存在 → 保留相对形式(不 fallback)
    assert p.exists()


def test_resolve_path_cwd_priority_nonempty_dir_with_kind(tmp_path, monkeypatch):
    # 与生产调用对齐:kind="dir" 且 CWD 下为非空目录 → 优先 CWD
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "x.jsonl").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert _resolve_path("logs", kind="dir") == Path("logs")


def test_resolve_path_falls_back_to_project_root(tmp_path, monkeypatch):
    # 在空临时目录(无 configs/)运行 → 回退项目根下的真实配置
    monkeypatch.chdir(tmp_path)
    p = _resolve_path("configs/entry_chain.dry_run_fib_pa_v1.json")
    assert p == (_PROJECT_ROOT / "configs/entry_chain.dry_run_fib_pa_v1.json")
    assert p.exists()


def test_resolve_path_missing_stays_relative(tmp_path, monkeypatch):
    # 两边都不存在时保持原样(让后续逻辑给出更明确的错误)
    monkeypatch.chdir(tmp_path)
    assert _resolve_path("no_such_dir/x.json") == Path("no_such_dir/x.json")


def test_resolve_path_empty_dir_does_not_shadow_logs(tmp_path, monkeypatch):
    # CWD 下同名空目录不得遮蔽项目根真实 logs(kind="dir" 校验 is_dir 且非空)
    (tmp_path / "logs").mkdir()
    monkeypatch.chdir(tmp_path)
    p = _resolve_path("logs", kind="dir")
    assert p == (_PROJECT_ROOT / "logs")
    assert p.is_dir() and any(p.iterdir())


def test_resolve_path_type_mismatch_file_kind(tmp_path, monkeypatch):
    # CWD 下同名文件 vs kind="dir" 类型不匹配 → 回退项目根
    (tmp_path / "logs").write_text("i am a file", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    p = _resolve_path("logs", kind="dir")
    assert p == (_PROJECT_ROOT / "logs")


def test_evaluate_script_shares_same_helper():
    # evaluate_offense_fixes.py 同款 helper 不漂移(import 级轻量检查)
    import scripts.evaluate_offense_fixes as ev

    assert callable(ev._resolve_path)
    assert ev._resolve_path("no_such_dir/x.json") == Path("no_such_dir/x.json")
