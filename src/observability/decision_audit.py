from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Mapping


GATE_REJECTION_FIELDS = ["timestamp", "symbol", "action", "score", "primary_reason", "reasons"]

# lean 模式下从 decisions.jsonl 每行移除的字段：
# - `s1_core`：S1 影子核快照（234 B/行），无任何分析脚本读取；
# - `component_points_v2_meta.volatility_regime_gauss_v2`：3 个 sigma 的敏感性中间值
#   （~150 B/行），`volatility_regime_clip_v1` 主值保留；
# - `warmup`：每行完全相同（132 B/行），只保留本 writer 的首行。
#
# 不要动 `component_points_v2` / `score_detail` / `entry_context` / `metadata` /
# `sizing_trace` / `weights` / `kline` / `reasons`——这些有分析脚本依赖。
_LEAN_ALWAYS_DROP = ("s1_core",)
# 2026-11-21 决定**不**剔除 `component_points_v2_meta.volatility_regime_gauss_v2`：
# 它只值 103 B/行（21 天约 3.6 MB），但 `scripts/analysis/stage_c_20261019.py:329`
# 会把它当描述性列 `v2_vol_gauss` 读走（缺失时静默变 None、不报错）。为了 3.6 MB
# 让一个分析列无解释地变空，不值得——瘦身的前提是"不破坏分析能力"。
_LEAN_META_DROP: tuple[str, ...] = ()


class DecisionAuditWriter:
    def __init__(self, output_dir: str | Path, *, lean: bool = False) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.lean = bool(lean)
        self._warmup_written = False
        self._decisions = (self.output_dir / "decisions.jsonl").open("a", encoding="utf-8")
        self._near_misses = (self.output_dir / "near_misses.jsonl").open("a", encoding="utf-8")
        self._gate_rejections = (self.output_dir / "gate_rejections.jsonl").open("a", encoding="utf-8")
        # lean：以下四个输出没有读取方（CSV 与 jsonl 重复），直接不打开、不写。
        self._drafts = None if self.lean else (self.output_dir / "order_drafts.jsonl").open("a", encoding="utf-8")
        self._attribution = None if self.lean else (self.output_dir / "attribution.jsonl").open("a", encoding="utf-8")
        self._scout_decisions = None if self.lean else (self.output_dir / "scout_decisions.jsonl").open("a", encoding="utf-8")
        self._gate_csv = None
        self._gate_csv_writer = None
        if not self.lean:
            gate_csv_path = self.output_dir / "gate_rejections.csv"
            needs_header = not gate_csv_path.exists() or gate_csv_path.stat().st_size == 0
            self._gate_csv = gate_csv_path.open("a", encoding="utf-8", newline="")
            self._gate_csv_writer = csv.DictWriter(self._gate_csv, fieldnames=GATE_REJECTION_FIELDS)
            if needs_header:
                self._gate_csv_writer.writeheader()
                self._gate_csv.flush()

    def write_decision(self, row: Mapping[str, object]) -> None:
        payload = self._prepare_decision(row)
        self._decisions.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        action = str(payload.get("action", ""))
        if action not in {"PROBE", "DIRECT"}:
            reasons = payload.get("reasons", [])
            reason_list = [str(item) for item in reasons] if isinstance(reasons, list) else [str(reasons)]
            gate_row = {
                "timestamp": payload.get("timestamp", ""),
                "symbol": payload.get("symbol", ""),
                "action": action,
                "score": payload.get("score", ""),
                "primary_reason": reason_list[0] if reason_list else "",
                "reasons": "|".join(reason_list),
            }
            self._gate_rejections.write(json.dumps(gate_row, ensure_ascii=False, sort_keys=True) + "\n")
            self._gate_rejections.flush()
            if self._gate_csv_writer is not None:
                self._gate_csv_writer.writerow(gate_row)
                self._gate_csv.flush()
        self._decisions.flush()

    def _prepare_decision(self, row: Mapping[str, object]) -> dict[str, object]:
        payload = dict(row)
        if not self.lean:
            return payload
        for key in _LEAN_ALWAYS_DROP:
            payload.pop(key, None)
        meta = payload.get("component_points_v2_meta")
        if isinstance(meta, Mapping):
            trimmed_meta = {k: v for k, v in meta.items() if k not in _LEAN_META_DROP}
            payload["component_points_v2_meta"] = trimmed_meta
        # 首行保留完整 warmup，其余写 null（值逐行相同，只需一份）。
        if self._warmup_written:
            payload["warmup"] = None
        else:
            self._warmup_written = True
        return payload

    def write_order_draft(self, row: Mapping[str, object]) -> None:
        if self._drafts is None:
            return
        self._drafts.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        self._drafts.flush()

    def write_attribution(self, row: Mapping[str, object]) -> None:
        if self._attribution is None:
            return
        self._attribution.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        self._attribution.flush()

    def write_near_miss(self, row: Mapping[str, object]) -> None:
        self._near_misses.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        self._near_misses.flush()

    def write_scout_decision(self, row: Mapping[str, object]) -> None:
        if self._scout_decisions is None:
            return
        self._scout_decisions.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        self._scout_decisions.flush()

    def close(self) -> None:
        self._decisions.close()
        self._near_misses.close()
        self._gate_rejections.close()
        for handle in (self._drafts, self._attribution, self._scout_decisions, self._gate_csv):
            if handle is not None:
                handle.close()

    def __enter__(self) -> "DecisionAuditWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
