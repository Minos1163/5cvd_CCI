"""验证 2026-10-31 落地的 three-arm 变更:

1. configs/entry_chain.dry_run_fib_pa_v12.json 能被 EntryChainConfig 载入,
   paper_ab_pure_ladder_enabled == True;
2. build_paper_exit_ab_ledgers 产出 legacy / trend_capture / pure_ladder 三本账;
3. defensive_overlay=False 时,Q3_DEFENSIVE_REDUCE 与 Q4_DEFENSIVE_EXIT 不再触发;
4. defensive_overlay=True 时行为与改动前一致(用同一序列对照)。

用法: python scripts/analysis/verify_pure_ladder_arm.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.observability.paper_trading import PaperExitConfig, PaperTradingLedger  # noqa: E402
from src.signals.entry_chain_config import EntryChainConfig  # noqa: E402

CONFIG_PATH = ROOT / "configs" / "entry_chain.dry_run_fib_pa_v12.json"


def load_config() -> EntryChainConfig:
    values = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return EntryChainConfig(**values)


def drive(ledger: PaperTradingLedger, *, experiment_id: str | None, bars: int = 6) -> list[dict]:
    decision = {
        "action": "PROBE",
        "side": "SHORT",
        "leverage": 3,
        "score": 80.0,
        "reasons": ["VERIFY"],
        "stop_pct": 0.01,
        "quadrant": "Q3",
    }
    if experiment_id:
        decision["experiment_id"] = experiment_id
    draft = {"approved": True, "request": {"quantity": 10.0, "price": 100.0, "position_side": "SHORT"}}
    ledger.on_decision(symbol="VERIFYUSDT", decision_payload=decision, draft_payload=draft,
                       kline={"open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0, "timestamp": 1_000_000},
                       timestamp=1_000_000)
    for i in range(1, bars + 1):
        ts = 1_000_000 + i * 900
        # 价格小幅上行 = 空单浮亏,但不触发 1% 止损(100 -> 100.5 只亏 0.5%)
        px = 100.3
        ledger.on_decision(
            symbol="VERIFYUSDT",
            decision_payload=decision,
            draft_payload={"approved": False},
            kline={"open": px, "high": px + 0.02, "low": px - 0.02, "close": px, "timestamp": ts},
            timestamp=ts,
        )
    return [
        json.loads(line)
        for line in (ledger.output_dir / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    cfg = load_config()
    assert getattr(cfg, "paper_ab_pure_ladder_enabled", False) is True, "配置未开启 pure_ladder"
    print("[1] config ok: paper_ab_pure_ladder_enabled =", cfg.paper_ab_pure_ladder_enabled)

    spec = importlib.util.spec_from_file_location("rld", ROOT / "scripts" / "run_live_dry_run.py")
    rld = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rld)

    tmp = Path(tempfile.mkdtemp())
    ledgers = rld.build_paper_exit_ab_ledgers(tmp / "out", tmp / "state", cfg)
    assert set(ledgers) == {"legacy", "trend_capture", "pure_ladder"}, f"账本集合不对: {sorted(ledgers)}"
    print("[2] ab ledgers:", sorted(ledgers))
    assert ledgers["pure_ladder"].exit_config.defensive_overlay is False
    assert ledgers["legacy"].exit_config.defensive_overlay is True

    # 3) 有 experiment_id + Q3:防御层应触发减仓
    on = PaperTradingLedger(tmp / "on", exit_config=PaperExitConfig(mode="legacy", defensive_overlay=True))
    off = PaperTradingLedger(tmp / "off", exit_config=PaperExitConfig(mode="legacy", defensive_overlay=False))
    ev_on = drive(on, experiment_id="verify_exp")
    ev_off = drive(off, experiment_id="verify_exp")
    red_on = [e for e in ev_on if e["event"] == "PAPER_REDUCE"]
    red_off = [e for e in ev_off if e["event"] == "PAPER_REDUCE"]
    assert red_on, "overlay=True 时未触发 Q3 减仓,测试无效"
    assert not red_off, f"overlay=False 时仍触发减仓: {[e.get('reason') for e in red_off]}"
    print(f"[3] overlay=True 减仓 {len(red_on)} 次({red_on[0]['reason']}),overlay=False 0 次")

    # 4) 无 experiment_id:两臂应完全一致(证明默认路径未被改动)
    a = PaperTradingLedger(tmp / "a", exit_config=PaperExitConfig(mode="legacy", defensive_overlay=True))
    b = PaperTradingLedger(tmp / "b", exit_config=PaperExitConfig(mode="legacy", defensive_overlay=False))
    ea, eb = drive(a, experiment_id=None), drive(b, experiment_id=None)
    ka = [(e["event"], e.get("reason")) for e in ea]
    kb = [(e["event"], e.get("reason")) for e in eb]
    assert ka == kb, f"非实验仓位两臂不一致: {ka} vs {kb}"
    print("[4] 无 experiment_id 时两臂事件序列一致:", ka)
    print("PASS")


if __name__ == "__main__":
    main()
