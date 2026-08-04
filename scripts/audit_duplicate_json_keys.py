# -*- coding: utf-8 -*-
"""JSON 重复键审计脚本。

背景: Claude 评审报告(2026-08-04 第 9 节)将 configs/entry_chain.dry_run_fib_pa_v1.json 中
  probe_conditions.long_threshold_offset=7.0 与顶层 long_threshold_offset=10.0 误判为"重复键"。
  核实结论: 二者位于不同 JSON 对象, 属于有意的两层设计(PROBE 层偏移 vs direct/watch 层偏移),
  **不是 JSON 重复键**, 删除任一都会改变行为。

本脚本只将【同一对象内】重复键视为错误(JSON 解析语义: 后者覆盖前者, 属静默冲突);
  【不同对象】同名键仅作为 info 提示输出, 不视为错误。

用法:
  python scripts/audit_duplicate_json_keys.py                # 扫描 configs/*.json
  python scripts/audit_duplicate_json_keys.py <file> ...     # 指定文件
  python scripts/audit_duplicate_json_keys.py --strict <f>   # 将同名键提示也视为错误(默认关闭)

退出码: 0 = 无同一对象内重复键; 1 = 发现同一对象内重复键。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def scan_file(path: Path) -> tuple[list[str], list[str]]:
    """返回 (同一对象内重复键列表, 同名键不同对象提示列表)。"""
    text = path.read_text(encoding="utf-8")
    duplicate_in_same_object: list[str] = []
    same_name_cross_object: Counter[str] = Counter()

    def hook(pairs):
        keys = [k for k, _ in pairs]
        counts = Counter(keys)
        for k, c in counts.items():
            if c > 1:
                duplicate_in_same_object.append(f"{k} (x{c})")
        for k, _ in pairs:
            same_name_cross_object[k] += 1
        return dict(pairs)

    json.loads(text, object_pairs_hook=hook)
    cross_info = [f"{k} (x{c})" for k, c in same_name_cross_object.items() if c > 1]
    return duplicate_in_same_object, cross_info


def main() -> int:
    parser = argparse.ArgumentParser(description="JSON 重复键审计(仅同一对象内重复视为错误)")
    parser.add_argument("files", nargs="*", help="JSON 文件路径;缺省扫描 configs/*.json")
    parser.add_argument("--strict", action="store_true", help="将不同对象同名键提示也视为错误")
    args = parser.parse_args()

    files = [Path(f) for f in args.files] if args.files else sorted(Path("configs").glob("*.json"))
    if not files:
        print("ERROR: 未找到配置文件", file=sys.stderr)
        return 1

    rc = 0
    for path in files:
        try:
            dup, cross = scan_file(path)
        except json.JSONDecodeError as e:
            print(f"[FAIL] {path}: JSON 解析失败 {e}", file=sys.stderr)
            rc = 1
            continue
        status = "OK" if not dup and not (args.strict and cross) else "FAIL"
        if status == "FAIL":
            rc = 1
        print(f"[{status}] {path}")
        for d in dup:
            print(f"    重复键(同一对象内, 后者生效): {d}")
        for c in cross:
            print(f"    info 同名键(不同对象, 设计允许): {c}")
    print(f"exit={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
