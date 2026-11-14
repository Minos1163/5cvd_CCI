"""报告口径守卫（P0 A7）：reporting 层不得把杠杆双计的 `margin_pnl` 系列当收益主张。

背景（2026-11-14 评审 §14 P0 A7）：`paper_trading` 的 PAPER_* 事件同时写了两套盈亏：

- `net_pnl` / `net_pnl_full`（**收益口径**，已扣成本、与权益变动可对齐）；
- `margin_pnl` / `realized_margin_pnl`（**杠杆双计口径**：`net_pnl × leverage`，
  在跨杠杆、跨标的加总时会把"杠杆倍数"当成收益放大，2026-10-31 评审已判为错误口径）。

历史上报告脚本混用过两套，导致"策略收益"可被杠杆选择抬升。现在报告层统一用
`net_pnl*` 口径，本测试把它钉住：**只要 reporting 层出现对 `margin_pnl` 系列的读取
（属性访问或字符串下标），就红**。

## 边界：「展示可以，主张不行」

 `margin_equity`（以及 `margin_used` 这类保证金占用字段）**不是**禁读项：
它只是"账面权益/占用保证金"的另一种表述，出现在报表里展示完全合法，
只是不能拿它当收益率的分母去做收益主张或跨标的比较。

真正禁读的是 `margin_pnl` / `realized_margin_pnl` / `position_margin_realized_pnl` ——
这三个是 `net_pnl × leverage` 的双计值，**任何收益结论用它都是错的**（它会把杠杆
选择伪装成 alpha）。所以：

| 字段 | 能否出现在报表 | 能否作为收益依据 |
|---|---|---|
| `net_pnl` / `net_pnl_full` | 能 | **能**（唯一合法收益口径） |
| `margin_equity` / `margin_used` | 能 | 不能当收益分母 |
| `margin_pnl` / `realized_margin_pnl` / `position_margin_realized_pnl` | 不应读取 | **不能** |

（2026-11-14 修正：上一版把 `margin_equity` 也列进禁读集合，是任务书写错；
风控复核指出它与 `margin_pnl` 性质不同，已移除。）

设计要点：只查 AST 节点，不扫原文。docstring / 注释里提到 `margin_pnl` 是**允许**的——
`ledger_metrics.py` 的模块注释就解释了为什么不用它，扫原文会误报，并逼迫人们删掉这段
最该保留的说明。

允许的写法（不是"读取字段值"）：
- `"margin_pnl" in row`（存在性判断，做数据体检）
- `row.get("margin_pnl")` —— **算读取**，禁止
- `row["margin_pnl"]` —— 算读取，禁止
- `obj.margin_pnl` —— 算读取，禁止
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# 报告层（口径必须统一的地方）。新增报告脚本时请加进来。
GUARDED_SOURCES = (
    "src/reporting/ledger_metrics.py",
    "src/reporting/performance_summary.py",
    "src/reporting/trade_journal.py",
    "scripts/report_strategy_review.py",
)

# 只禁"杠杆双计的收益主张"。`margin_equity` / `margin_used` 属"可展示"类，不在其中。
FORBIDDEN_NAMES = frozenset({
    "margin_pnl",
    "realized_margin_pnl",
    "position_margin_realized_pnl",
})

# 明确允许出现的保证金口径字段（写在这里是为了让后来人不必猜）。
DISPLAY_ONLY_NAMES = frozenset({"margin_equity", "margin_used"})


def _iter_forbidden_reads(source: str, path: str):
    """产出 (行号, 字段名, 违规形态) —— 只认"取值"形态，不认存在性判断。"""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # obj.margin_pnl
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            yield node.lineno, node.attr, f"{path} 属性访问"
        # row["margin_pnl"]
        elif isinstance(node, ast.Subscript):
            key = node.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value in FORBIDDEN_NAMES:
                yield node.lineno, key.value, f"{path} 字符串下标"
        # row.get("margin_pnl") / getattr(row, "margin_pnl")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in {"get", "pop", "setdefault"} and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value in FORBIDDEN_NAMES:
                    yield node.lineno, first.value, f"{path} dict.{name}()"
            if name == "getattr" and len(node.args) >= 2:
                second = node.args[1]
                if isinstance(second, ast.Constant) and isinstance(second.value, str) and second.value in FORBIDDEN_NAMES:
                    yield node.lineno, second.value, f"{path} getattr()"


@pytest.mark.parametrize("relative_path", GUARDED_SOURCES)
def test_reporting_layer_never_reads_margin_pnl_fields(relative_path: str) -> None:
    path = ROOT / relative_path
    assert path.exists(), f"报告层文件不存在，检查清单是否过期: {relative_path}"
    source = path.read_text(encoding="utf-8")
    offenders = [
        f"第 {line} 行读取 {name!r}（{form}）"
        for line, name, form in _iter_forbidden_reads(source, relative_path)
    ]
    assert not offenders, (
        f"{relative_path} 读了杠杆双计口径字段，报告必须统一用 net_pnl*/margin_equity:\n"
        + "\n".join(offenders)
    )


def test_guard_actually_detects_reads(tmp_path: Path) -> None:
    """反证：守卫本身必须能抓到读法，否则"全绿"没有意义。"""
    bad_source = (
        "def f(row):\n"
        "    a = row['margin_pnl']\n"
        "    b = row.get('realized_margin_pnl')\n"
        "    c = row['position_margin_realized_pnl']\n"
        "    d = getattr(row, 'margin_pnl', None)\n"
        "    return a, b, c, d\n"
    )
    found = sorted(name for _line, name, _form in _iter_forbidden_reads(bad_source, "bad.py"))
    assert found == ["margin_pnl", "margin_pnl", "position_margin_realized_pnl", "realized_margin_pnl"]


def test_margin_equity_is_display_only_not_forbidden() -> None:
    """「展示可以，主张不行」：读 `margin_equity` 不违规，读 `margin_pnl` 才违规。

    这条是 2026-11-14 修正的守卫：上一版把 `margin_equity` 也禁掉，
    会让报告连"保证金占用/账面权益"都不能展示——那是合法的账面信息。
    """
    source = (
        "def f(row):\n"
        "    equity = row['margin_equity']\n"
        "    used = row.margin_used\n"
        "    return equity, used\n"
    )
    assert list(_iter_forbidden_reads(source, "ok.py")) == []
    assert "margin_equity" not in FORBIDDEN_NAMES
    assert "margin_equity" in DISPLAY_ONLY_NAMES
    # 但同一个文件里一旦读了 margin_pnl，仍然要红
    mixed = "def g(row):\n    a = row['margin_equity']\n    b = row['margin_pnl']\n    return a, b\n"
    found = [name for _line, name, _form in _iter_forbidden_reads(mixed, "mixed.py")]
    assert found == ["margin_pnl"]


def test_guard_allows_docstring_and_presence_checks() -> None:
    """只提到名字 / 只做存在性判断，不算读取。"""
    ok_source = (
        '"""margin_pnl 已被判定为杠杆双计口径，本模块只用 net_pnl。"""\n'
        "def f(row):\n"
        "    # margin_pnl / realized_margin_pnl 不参与收益计算\n"
        "    if 'margin_pnl' in row:\n"
        "        return 1\n"
        "    return row['net_pnl']\n"
    )
    assert list(_iter_forbidden_reads(ok_source, "ok.py")) == []


def test_ledger_metrics_uses_net_pnl_basis() -> None:
    """正例锚点：ledger_metrics 确实在用收益口径，别让守卫变成"什么都没查"。"""
    source = (ROOT / "src/reporting/ledger_metrics.py").read_text(encoding="utf-8")
    assert "net_pnl" in source
    tree = ast.parse(source)
    names = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("net_pnl")
    }
    assert names, "ledger_metrics 里找不到 net_pnl* 字段读取，口径可能又变了"
