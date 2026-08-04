# -*- coding: utf-8 -*-
"""实施追踪协议 — 防止诊断报告的建议再次未落地。

依据: docs/2026-08-04-implementation-gap-and-asymmetric-fix-recommendations.md 第 8 节
  - 每条 P0/P1 建议必须有追踪记录
  - 生成新诊断报告前, 必须检查 P0 建议是否已 DEPLOYED/VERIFIED
  - 任何 P0 仍为 PENDING/IN_PROGRESS 时, 新报告开篇必须说明, 不得默默跳过

数据源: docs/recommendations_tracking.md(人类可读表格, 也是报告开篇"上轮建议实施回顾"的格式)

用法:
  python scripts/recommendation_tracker.py list          # 列出全部建议
  python scripts/recommendation_tracker.py check         # 报告前阻塞检查(退出码 0=通过, 1=存在未解决 P0)
  python scripts/recommendation_tracker.py show <id>     # 显示单条

表格列(与 tracking.md 一致):
  | 建议ID | 报告日期 | 优先级 | 内容摘要 | 目标代码位置 | 实施状态 | 验证结果 |
状态枚举: PENDING / IN_PROGRESS / DEPLOYED / VERIFIED / ABANDONED
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

TRACKING_FILE = Path("docs/recommendations_tracking.md")
COLUMNS = ["id", "report_date", "priority", "description", "target", "status", "verification"]
STATUSES = ("PENDING", "IN_PROGRESS", "DEPLOYED", "VERIFIED", "ABANDONED")


@dataclass
class Recommendation:
    id: str
    report_date: str
    priority: str
    description: str
    target: str
    status: str = "PENDING"
    verification: str = "N/A"

    @property
    def is_resolved(self) -> bool:
        return self.status in ("DEPLOYED", "VERIFIED", "ABANDONED")

    def to_row(self) -> str:
        cells = [
            self.id, self.report_date, self.priority, self.description,
            self.target, self.status, self.verification,
        ]
        return "| " + " | ".join(cells) + " |"


def parse_tracking_table(text: str) -> list[Recommendation]:
    """解析 tracking.md 中的表格行(跳过标题行与分隔行)。"""
    recs: list[Recommendation] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 7:
            continue
        if cells[0].startswith("建议ID") or set(cells[0]) <= {"-", ":"}:
            continue  # 表头或分隔行
        recs.append(Recommendation(
            id=cells[0], report_date=cells[1], priority=cells[2],
            description=cells[3], target=cells[4], status=cells[5],
            verification=cells[6] if len(cells) > 6 else "N/A",
        ))
    return recs


def load_recommendations(tracking_file: Path = TRACKING_FILE) -> list[Recommendation]:
    if not tracking_file.exists():
        print(f"ERROR: 追踪表不存在: {tracking_file}", file=sys.stderr)
        sys.exit(2)
    return parse_tracking_table(tracking_file.read_text(encoding="utf-8"))


def check_blocking(recs: list[Recommendation]) -> list[Recommendation]:
    """报告前检查: 返回未解决(非 DEPLOYED/VERIFIED/ABANDONED)的 P0 建议。"""
    return [r for r in recs if r.priority.upper() == "P0" and not r.is_resolved]


def cmd_list(recs: list[Recommendation]) -> None:
    print("| 建议ID | 报告日期 | 优先级 | 内容摘要 | 目标代码位置 | 实施状态 | 验证结果 |")
    print("|---|---|---|---|---|---|---|")
    for r in sorted(recs, key=lambda x: (x.priority, x.id)):
        print(r.to_row())


def cmd_check(recs: list[Recommendation]) -> int:
    blocking = check_blocking(recs)
    if not blocking:
        print("OK: 无未解决的 P0 建议, 可以生成新报告。")
        return 0
    print(f"BLOCK: {len(blocking)} 条 P0 建议未解决(DEPLOYED/VERIFIED/ABANDONED 之外), 新报告开篇必须说明:")
    for r in blocking:
        print(f"  - {r.id} [{r.status}] {r.description} -> {r.target}")
    return 1


def cmd_show(recs: list[Recommendation], rid: str) -> int:
    for r in recs:
        if r.id == rid:
            print(f"id:            {r.id}")
            print(f"report_date:   {r.report_date}")
            print(f"priority:      {r.priority}")
            print(f"description:   {r.description}")
            print(f"target:        {r.target}")
            print(f"status:        {r.status}")
            print(f"verification:  {r.verification}")
            return 0
    print(f"ERROR: 未找到建议 {rid}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="实施追踪协议检查")
    parser.add_argument("command", choices=["list", "check", "show"], help="list=全部, check=报告前阻塞检查, show=<id>")
    parser.add_argument("id", nargs="?", default=None)
    args = parser.parse_args()

    recs = load_recommendations()
    if args.command == "list":
        cmd_list(recs)
        return 0
    if args.command == "check":
        return cmd_check(recs)
    if args.command == "show":
        if not args.id:
            print("ERROR: show 需要建议ID", file=sys.stderr)
            return 1
        return cmd_show(recs, args.id)
    return 1


if __name__ == "__main__":
    sys.exit(main())
