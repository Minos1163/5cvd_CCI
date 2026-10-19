"""冻结当前分析结论为基线快照(在改成本口径 / 显著性口径之前)。

为什么需要
----------
下一步要做的两件事会**改变结论口径**:

1. 成本分档:把固定的 20bps 换成按流动性分档(12/20/30bps),
   所有 ``E[R_net]`` 都会整体下移,跨报告的数字不再可比;
2. 日块置换:把显著性检验的独立单元从 ``symbol|utc_date`` 换成 UTC 日,
   同一天多标的的截面相关不再被当成独立样本,p 值会系统性变大。

改口径之前必须把**旧口径下的结论**原样存档,否则事后无法回答
"这个结论是新口径带来的,还是本来就那样"。

logs/ 被 .gitignore 排除,所以把冻结副本放进 docs/analysis/baseline/<date>/ 才进得了版本库。

用法
----
    python scripts/analysis/freeze_baseline_20261019.py            # 冻结
    python scripts/analysis/freeze_baseline_20261019.py --verify   # 校验副本与源一致
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATE = "2026-10-19"
BASE = ROOT / "docs" / "analysis" / "baseline" / DATE

# (源路径, 冻结副本相对路径)
SOURCES: list[tuple[str, str]] = [
    ("docs/analysis/cost_audit_2026-10-19.md", "docs/cost_audit_2026-10-19.md"),
    ("docs/analysis/fwd_label_v2_2026-10-19.md", "docs/fwd_label_v2_2026-10-19.md"),
    ("docs/analysis/ic_term_structure_2026-10-19.md", "docs/ic_term_structure_2026-10-19.md"),
    ("docs/analysis/stage_c_2026-10-19.md", "docs/stage_c_2026-10-19.md"),
    ("docs/analysis/six_factor_1h_2026-10-19.md", "docs/six_factor_1h_2026-10-19.md"),
    ("docs/analysis/stop_floor_and_edge_scan_2026-10-19.md", "docs/stop_floor_and_edge_scan_2026-10-19.md"),
    ("docs/analysis/stop_floor_cost_tf_uplift_2026-10-19.md", "docs/stop_floor_cost_tf_uplift_2026-10-19.md"),
    ("docs/analysis/relabel_2026-10-19.md", "docs/relabel_2026-10-19.md"),
    ("docs/analysis/2026-10-04_to_10-18_loss_attribution.md", "docs/2026-10-04_to_10-18_loss_attribution.md"),
    ("docs/analysis/2026-10-18-review-erratum-and-revision.md", "docs/2026-10-18-review-erratum-and-revision.md"),
    ("logs/analysis/strategy-audit-2026-10-19.md", "snapshots/strategy-audit-2026-10-19.md"),
    ("logs/analysis/gate-controls/2026-10-19/report.md", "snapshots/gate-controls-report.md"),
    ("logs/analysis/risk-first/2026-10-19/report.md", "snapshots/risk-first-report.md"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
        )
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def freeze() -> None:
    rows: list[tuple[str, str, str]] = []
    missing: list[str] = []
    for source, target in SOURCES:
        src = ROOT / source
        if not src.exists():
            missing.append(source)
            continue
        dst = BASE / target
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        rows.append((source, target, sha256(src)))

    lines = [
        f"# 基线冻结 {DATE}",
        "",
        f"- 冻结时间:{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"- 冻结时 HEAD:`{git_head()}`",
        "- 冻结原因:下一步要做**成本分档**(20bps → 12/20/30 按流动性分档)与"
        "**日块置换**(显著性独立单元由 `symbol|utc_date` 改为 UTC 日)。"
        "两者都会改变结论口径,改之前先把旧口径结论原样存档。",
        "- `logs/` 被 .gitignore 排除,所以冻结副本放在 `docs/analysis/baseline/` 才会进版本库。",
        "",
        "## 旧口径的两个前提(新口径下不再成立)",
        "",
        "1. **成本**:全部标的统一 20bps(单边,含费+滑点)。新口径下低流动性标的更贵,"
        "所有 `E[R_net]` 整体下移约 0.02R,**跨报告数字不可直接比较**。",
        "2. **显著性**:以 `symbol|utc_date` 为独立单元的 bootstrap。同日多标的存在截面相关,"
        "该口径会低估 p 值;日块置换后 p 值系统性变大。",
        "",
        "## 清单(sha256 校验源与副本一致)",
        "",
        "| 源文件 | 冻结副本 | sha256 前 16 位 |",
        "|---|---|---|",
    ]
    for source, target, digest in rows:
        lines.append(f"| `{source}` | `{target}` | `{digest[:16]}` |")
    if missing:
        lines.append("")
        lines.append("## 缺失(冻结时不存在)")
        lines.append("")
        for item in missing:
            lines.append(f"- `{item}`")
    lines.append("")
    lines.append("## 回退方式")
    lines.append("")
    lines.append("```bash")
    lines.append(f"git show HEAD:docs/analysis/baseline/{DATE}/docs/cost_audit_2026-10-19.md")
    lines.append("```")
    lines.append("")
    (BASE / "MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[freeze] {len(rows)} files -> {BASE}")
    for item in missing:
        print(f"[skip] {item}")


def verify() -> None:
    bad: list[str] = []
    for source, target in SOURCES:
        src = ROOT / source
        dst = BASE / target
        if not src.exists() or not dst.exists():
            bad.append(f"missing: {source}")
            continue
        if sha256(src) != sha256(dst):
            bad.append(f"drift: {source}")
    print("[verify] OK" if not bad else "[verify] FAILED")
    for item in bad:
        print(f"  - {item}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    verify() if args.verify else freeze()
