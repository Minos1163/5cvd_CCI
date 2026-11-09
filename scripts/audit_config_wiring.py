#!/usr/bin/env python3
"""静态审计 EntryChainConfig 的字段是否真的被代码读取。

背景: ``configs/entry_chain*.json`` 里写满键,不等于代码会读它。历史上多次出现
"死配置被当成有效机制"。本工具用 AST 机械地列出 ``EntryChainConfig`` 的每个字段
在 ``src/**/*.py`` 与 ``scripts/**/*.py`` 中是否存在读取点。

输出:
  - ``docs/audit/config-wiring-<YYYYMMDD>.json``
  - ``docs/audit/config-wiring-<YYYYMMDD>.md``
  - 终端摘要: ``fields=N live=M declared_only=K unknown_keys=0``

已知局限(必须随报告一起读):
  DECLARED_ONLY 的含义是"静态不可见",**不是**"确定未使用"。以下动态读取方式
  本工具扫不到:
    * ``getattr(cfg, name)`` / ``vars(cfg)`` / ``asdict(cfg)`` / ``**cfg``
    * 变量名不以 ``cfg``/``config`` 结尾的持有者(如 ``self.entry_chain.xxx``)
  因此 DECLARED_ONLY 只能作为"待人工确认"的候选清单。

纯标准库,无网络,不 import 被测模块(避免执行副作用)。
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

DEFAULT_CLASS_NAME = "EntryChainConfig"
SCAN_ROOTS = ("src", "scripts")
CONFIG_GLOB = "entry_chain*.json"
# 配置文件自身的 from_mapping 会遍历所有字段,如果计入会把全部字段误判为 LIVE_READ。
EXCLUDED_PATHS = ("src/signals/entry_chain_config.py",)
EXCLUDED_DIR_NAMES = {"__pycache__", "tests"}
MAX_LOCATIONS = 5

LIVE_READ = "LIVE_READ"
DYNAMIC_READ = "DYNAMIC_READ"  # 只有 getattr/vars 之类动态路径命中
DECLARED_ONLY = "DECLARED_ONLY"


# --------------------------------------------------------------------------
# 纯函数:字段提取
# --------------------------------------------------------------------------
def extract_fields(source: str, class_name: str = DEFAULT_CLASS_NAME) -> list[str]:
    """从模块源码里提取指定 dataclass 的 ``AnnAssign`` 字段名(按声明顺序)。"""
    tree = ast.parse(source)
    class_node = _find_class(tree, class_name)
    names: list[str] = []
    seen: set[str] = set()
    for stmt in class_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            name = stmt.target.id
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _find_class(tree: ast.Module, class_name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise ValueError(f"class {class_name!r} not found at module level")


# --------------------------------------------------------------------------
# 纯函数:读取点收集与分类
# --------------------------------------------------------------------------
def _is_config_holder(node: ast.AST) -> bool:
    """``cfg`` / ``config`` / ``self.config`` / ``entry_cfg`` 之类的持有者表达式。"""
    try:
        text = ast.unparse(node).strip()
    except Exception:  # pragma: no cover - 极端畸形 AST
        return False
    last = text.split(".")[-1].strip().lower()
    if not last.isidentifier():
        return False
    return last.endswith("cfg") or last.endswith("config")


def _constant_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _collect_reads_from_tree(
    tree: ast.AST,
    fields: set[str],
    relpath: str,
) -> tuple[dict[str, list[tuple[str, str]]], dict[str, list[tuple[str, str]]]]:
    """返回 (直接读取, 动态读取)，每项都是 {字段名: [(位置, via), ...]}。

    直接读取 = 属性访问 / dict key 读取，运行时**一定**读到该字段。
    动态读取 = ``getattr(cfg, "x")`` / ``vars(cfg).get("x")`` 这类：
    静态可见其存在，但运行时是否命中取决于数据，不能断言。
    两者分开记，是为了让"未接线"这个结论只落在两遍都扫不到的字段上。
    """
    direct: dict[str, set[tuple[str, str]]] = defaultdict(set)
    dynamic: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in fields and _is_config_holder(node.value):
                direct[node.attr].add((f"{relpath}:{node.lineno}", "attribute"))
        elif isinstance(node, ast.Call):
            func = node.func
            # getattr(holder, "field", default?)
            if isinstance(func, ast.Name) and func.id == "getattr" and len(node.args) >= 2:
                holder, key = node.args[0], _constant_str(node.args[1])
                if key in fields and _is_config_holder(holder):
                    dynamic[key].add((f"{relpath}:{node.lineno}", "getattr"))
            # <holder>.get("field") / vars(holder).get("field")
            if isinstance(func, ast.Attribute) and func.attr == "get" and node.args:
                key = _constant_str(node.args[0])
                if key in fields:
                    holder = func.value
                    if isinstance(holder, ast.Call) and isinstance(holder.func, ast.Name) and holder.func.id == "vars":
                        if holder.args and _is_config_holder(holder.args[0]):
                            dynamic[key].add((f"{relpath}:{node.lineno}", "vars"))
                            continue
                    # 与下标同理：不校验持有者，避免漏掉"配置摊平成 dict 再取键"的链
                    direct[key].add((f"{relpath}:{node.lineno}", "dict_get"))
        elif isinstance(node, ast.Subscript):
            # 下标读取**不校验持有者**：配置可能先被摊平成普通 dict 再逐键取出，
            # 若严格要求 holder 以 cfg/config 结尾会漏掉这条链。代价是：与配置键
            # 同名的无关 dict（如 row["score"]）也会被算作读取点 —— 这个方向的
            # 误差是"把死键误报成活的"，比反过来更保守，已在 limitations 里声明。
            key = _constant_str(node.slice)
            if key in fields:
                direct[key].add((f"{relpath}:{node.lineno}", "subscript"))
    return (
        {k: sorted(v) for k, v in direct.items()},
        {k: sorted(v) for k, v in dynamic.items()},
    )


def _sort_locations(locations: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    def key(item: tuple[str, str]) -> tuple[str, int]:
        path, _, line = item[0].rpartition(":")
        return path, int(line) if line.isdigit() else 0

    return sorted(set(locations), key=key)


def classify(
    sources: Mapping[str, str],
    fields: Iterable[str],
    exclude: Iterable[str] = (),
) -> dict[str, dict[str, Any]]:
    """对每个字段分类,返回 {字段: {status, read_count, locations, evidence, via}}。

    三值：
    - ``LIVE_READ``     —— 存在直接读取（属性访问 / dict key）
    - ``DYNAMIC_READ``  —— 只有 getattr/vars 等动态路径；静态可见、运行时不保证
    - ``DECLARED_ONLY`` —— 两遍都没扫到
    """
    field_list = list(dict.fromkeys(fields))
    field_set = set(field_list)
    excluded = {str(item).replace("\\", "/") for item in exclude}

    direct_all: dict[str, set[tuple[str, str]]] = {name: set() for name in field_list}
    dynamic_all: dict[str, set[tuple[str, str]]] = {name: set() for name in field_list}
    for relpath, source in sources.items():
        normalized = relpath.replace("\\", "/")
        if normalized in excluded:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        direct, dynamic = _collect_reads_from_tree(tree, field_set, normalized)
        for name, hits in direct.items():
            direct_all[name].update(hits)
        for name, hits in dynamic.items():
            dynamic_all[name].update(hits)

    result: dict[str, dict[str, Any]] = {}
    for name in field_list:
        direct_hits = _sort_locations(direct_all[name])
        dynamic_hits = _sort_locations(dynamic_all[name])
        if direct_hits:
            status = LIVE_READ
            hits = direct_hits
        elif dynamic_hits:
            status = DYNAMIC_READ
            hits = dynamic_hits
        else:
            status = DECLARED_ONLY
            hits = []
        result[name] = {
            "status": status,
            "read_count": len(direct_hits) + len(dynamic_hits),
            "locations": [loc for loc, _ in hits[:MAX_LOCATIONS]],
            "evidence": [{"location": loc, "via": via} for loc, via in hits[:MAX_LOCATIONS]],
            "via": sorted({via for _, via in hits}),
            # 即使已判 LIVE_READ，也把动态路径单独留证：
            # 它说明"这个字段除了静态可见的读取，还有一条取决于数据的分支"。
            "dynamic_evidence": [
                {"location": loc, "via": via} for loc, via in dynamic_hits[:MAX_LOCATIONS]
            ],
        }
    return result


# --------------------------------------------------------------------------
# 纯函数:未知键检测
# --------------------------------------------------------------------------
def find_unknown_keys(
    payloads: Mapping[str, Any],
    fields: Iterable[str],
) -> dict[str, list[str]]:
    """返回 {未知键: [出现的配置文件名...]},键与文件名均排序。"""
    field_set = set(fields)
    unknown: dict[str, list[str]] = defaultdict(list)
    for filename in sorted(payloads):
        payload = payloads[filename]
        if not isinstance(payload, Mapping):
            continue
        for key in payload:
            if key not in field_set:
                unknown[str(key)].append(filename)
    return {key: sorted(files) for key, files in sorted(unknown.items())}


# --------------------------------------------------------------------------
# 文件系统辅助
# --------------------------------------------------------------------------
def discover_sources(root: Path) -> dict[str, str]:
    """收集扫描范围内的 Python 源码,返回 {相对路径: 文本}。"""
    sources: dict[str, str] = {}
    for scan_root in SCAN_ROOTS:
        base = root / scan_root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            relpath = path.relative_to(root).as_posix()
            if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
                continue
            if relpath in EXCLUDED_PATHS:
                continue
            sources[relpath] = path.read_text(encoding="utf-8", errors="replace")
    return sources


def load_config_payloads(root: Path, configs_dir: Path | None = None) -> dict[str, Any]:
    """读取 configs 目录下 entry_chain*.json(顶层键)。解析失败的文件跳过并记录。

    ``configs_dir`` 缺省为 ``<root>/configs``；相对路径按 ``root`` 解释。
    """
    base = Path(configs_dir) if configs_dir is not None else root / "configs"
    if not base.is_absolute():
        base = root / base
    payloads: dict[str, Any] = {}
    for path in sorted(base.glob(CONFIG_GLOB)):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        payloads[path.name] = payload
    return payloads


def current_commit(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - 环境相关
        return "unknown"
    commit = completed.stdout.strip()
    return commit or "unknown"


def git_dirty(root: Path) -> bool:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - 环境相关
        return False
    return bool(completed.stdout.strip())


def _relative_root_label(root: Path) -> str:
    return root.name or "."


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------
def build_report(
    root: Path,
    class_source: str,
    sources: Mapping[str, str],
    payloads: Mapping[str, Any],
    class_name: str = DEFAULT_CLASS_NAME,
) -> dict[str, Any]:
    fields = extract_fields(class_source, class_name)
    excluded = set(EXCLUDED_PATHS)
    classification = classify(sources, fields, exclude=excluded)
    unknown_keys = find_unknown_keys(payloads, fields)

    field_rows = [
        {
            "name": name,
            "status": classification[name]["status"],
            "read_count": classification[name]["read_count"],
            "locations": classification[name]["locations"],
            "evidence": classification[name]["evidence"],
            "dynamic_evidence": classification[name]["dynamic_evidence"],
            "via": classification[name]["via"],
        }
        for name in sorted(classification)
    ]
    live = sum(1 for row in field_rows if row["status"] == LIVE_READ)
    dynamic = sum(1 for row in field_rows if row["status"] == DYNAMIC_READ)
    declared_only = len(field_rows) - live - dynamic

    return {
        "schema": "config-wiring-audit/v1",
        "generated_on": date.today().isoformat(),
        "root_label": _relative_root_label(root),
        "commit": current_commit(root),
        "git_dirty": git_dirty(root),
        "class_name": class_name,
        "fields_total": len(field_rows),
        "live_read": live,
        "dynamic_read": dynamic,
        "readable_total": live + dynamic,
        "declared_only": declared_only,
        "unknown_keys": len(unknown_keys),
        "unknown_key_details": unknown_keys,
        "files_scanned": len(sources),
        "config_files": sorted(payloads),
        "excluded_paths": sorted(excluded),
        "scan_roots": list(SCAN_ROOTS),
        "read_rules": [
            "Attribute: <holder>.<field> 且 holder 标识符以 cfg/config 结尾 -> LIVE_READ",
            "Call: <holder>.get(\"<field>\") -> LIVE_READ",
            "Subscript: <any>[\"<field>\"] -> LIVE_READ(不校验持有者)",
            "Call: getattr(<holder>, \"<field>\", ...) -> DYNAMIC_READ",
            "Call: vars(<holder>).get(\"<field>\") -> DYNAMIC_READ",
        ],
        "limitations": [
            "动态读取只能标记为 DYNAMIC_READ:静态可见其存在,运行时是否命中取决于数据",
            "持有者变量名必须以便以 cfg/config 结尾,否则漏检(如 self.entry_chain.x)",
            "下标读取不校验持有者,与配置键同名的无关 dict 会被算作读取点(偏保守,宁漏报死键)",
            "**cfg 展开、asdict(cfg) 后按键取值无法逐一归属,映射到全部字段 -> 不在此表",
            "DECLARED_ONLY 表示'静态与动态两遍都不可见',不等于'确定未使用',需人工确认",
        ],
        "fields": field_rows,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    rows = report["fields"]
    declared = [row for row in rows if row["status"] == DECLARED_ONLY]
    dynamic = [row for row in rows if row["status"] == DYNAMIC_READ]
    live = [row for row in rows if row["status"] == LIVE_READ]

    lines: list[str] = []
    lines.append("# EntryChainConfig 配置接线审计")
    lines.append("")
    lines.append(f"- 生成日期: {report['generated_on']}")
    lines.append(f"- commit: `{report['commit']}`(工作区有未提交改动: {report['git_dirty']})")
    lines.append(f"- 数据类: `{report['class_name']}`")
    lines.append(f"- 扫描文件数: {report['files_scanned']}")
    lines.append(
        f"- 字段总数: {report['fields_total']} | "
        f"LIVE_READ: {report['live_read']} | "
        f"DYNAMIC_READ: {report['dynamic_read']} | "
        f"DECLARED_ONLY: {report['declared_only']} | "
        f"UNKNOWN_KEY: {report['unknown_keys']}"
    )
    lines.append("")
    lines.append("> **三类状态**:`LIVE_READ` 有直接读取;`DYNAMIC_READ` 只有 `getattr`/`vars` 命中,")
    lines.append("> 静态可见但运行时是否命中取决于数据;`DECLARED_ONLY` 两遍都不可见。")
    lines.append("> **`DECLARED_ONLY` 是「待人工确认」的候选,不是死代码结论** —— 持有者变量名不以")
    lines.append("> `cfg`/`config` 结尾、或经 `**cfg` 展开读取时仍会漏检。")
    lines.append("")
    lines.append(f"## DYNAMIC_READ(仅动态路径,共 {len(dynamic)} 个)")
    lines.append("")
    if dynamic:
        lines.append("| # | 字段 | 命中方式 | 位置 |")
        lines.append("| --- | --- | --- | --- |")
        for index, row in enumerate(dynamic, start=1):
            via = "、".join(row.get("via") or []) or "-"
            locations = "<br>".join(f"`{loc}`" for loc in row["locations"]) or "-"
            lines.append(f"| {index} | `{row['name']}` | {via} | {locations} |")
    else:
        lines.append("(无)")
    lines.append("")
    lines.append(f"## DECLARED_ONLY(静态与动态两遍都不可见,共 {len(declared)} 个)")
    lines.append("")
    if declared:
        lines.append("| # | 字段 | 读取点数 |")
        lines.append("| --- | --- | --- |")
        for index, row in enumerate(declared, start=1):
            lines.append(f"| {index} | `{row['name']}` | {row['read_count']} |")
    else:
        lines.append("(无)")
    lines.append("")
    lines.append(f"## LIVE_READ(共 {len(live)} 个)")
    lines.append("")
    if live:
        lines.append("| # | 字段 | 读取点数 | 前几处位置 |")
        lines.append("| --- | --- | --- | --- |")
        for index, row in enumerate(live, start=1):
            locations = "<br>".join(f"`{loc}`" for loc in row["locations"]) or "-"
            lines.append(f"| {index} | `{row['name']}` | {row['read_count']} | {locations} |")
    else:
        lines.append("(无)")
    lines.append("")
    lines.append(f"## UNKNOWN_KEY(共 {report['unknown_keys']} 个)")
    lines.append("")
    if report["unknown_key_details"]:
        lines.append("| 键 | 出现的配置 |")
        lines.append("| --- | --- |")
        for key, files in report["unknown_key_details"].items():
            lines.append(f"| `{key}` | {', '.join(files)} |")
        lines.append("")
        lines.append("> 出现未知键时 `EntryChainConfig.from_mapping()` 会直接抛 `ValueError`,对应配置无法启动。")
    else:
        lines.append("(无,所有配置键都在数据类中声明)")
    lines.append("")
    lines.append("## 扫描口径")
    lines.append("")
    lines.append(f"- 扫描根: {', '.join(f'`{item}/**/*.py`' for item in report['scan_roots'])}")
    lines.append(f"- 排除: {', '.join(f'`{item}`' for item in report['excluded_paths'])}、`__pycache__/`、`tests/`")
    lines.append(f"- 配置来源: {', '.join(f'`{item}`' for item in report['config_files']) or '(无)'}")
    lines.append("- 读取点判定规则:")
    for rule in report["read_rules"]:
        lines.append(f"  - {rule}")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="静态审计 EntryChainConfig 字段是否被读取")
    parser.add_argument("--root", default=None, help="仓库根目录(默认自动探测)")
    parser.add_argument(
        "--configs-dir",
        default=None,
        help="配置文件目录(默认 <root>/configs;相对路径按 root 解释)",
    )
    parser.add_argument("--out-dir", default="docs/audit", help="报告输出目录(相对仓库根)")
    parser.add_argument(
        "--fail-on-unknown-key",
        action="store_true",
        help="存在未知配置键时返回码 1",
    )
    return parser.parse_args(argv)


def default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve() if args.root else default_root()
    class_path = root / EXCLUDED_PATHS[0]
    if not class_path.is_file():
        print(f"error: 找不到数据类定义文件: {class_path}", file=sys.stderr)
        return 2

    class_source = class_path.read_text(encoding="utf-8")
    sources = discover_sources(root)
    payloads = load_config_payloads(root, Path(args.configs_dir) if args.configs_dir else None)
    report = build_report(root, class_source, sources, payloads)

    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"config-wiring-{date.today():%Y%m%d}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(
        f"fields={report['fields_total']} live={report['live_read']} "
        f"dynamic={report['dynamic_read']} declared_only={report['declared_only']} "
        f"unknown_keys={report['unknown_keys']}"
    )
    print(f"json: {json_path.relative_to(root).as_posix()}")
    print(f"md:   {md_path.relative_to(root).as_posix()}")

    if args.fail_on_unknown_key and report["unknown_keys"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
