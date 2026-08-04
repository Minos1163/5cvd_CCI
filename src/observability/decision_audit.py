from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Mapping


GATE_REJECTION_FIELDS = ["timestamp", "symbol", "action", "score", "primary_reason", "reasons"]


class DecisionAuditWriter:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._decisions = (self.output_dir / "decisions.jsonl").open("a", encoding="utf-8")
        self._drafts = (self.output_dir / "order_drafts.jsonl").open("a", encoding="utf-8")
        self._attribution = (self.output_dir / "attribution.jsonl").open("a", encoding="utf-8")
        self._near_misses = (self.output_dir / "near_misses.jsonl").open("a", encoding="utf-8")
        self._scout_decisions = (self.output_dir / "scout_decisions.jsonl").open("a", encoding="utf-8")
        self._gate_rejections = (self.output_dir / "gate_rejections.jsonl").open("a", encoding="utf-8")
        gate_csv_path = self.output_dir / "gate_rejections.csv"
        needs_header = not gate_csv_path.exists() or gate_csv_path.stat().st_size == 0
        self._gate_csv = gate_csv_path.open("a", encoding="utf-8", newline="")
        self._gate_csv_writer = csv.DictWriter(self._gate_csv, fieldnames=GATE_REJECTION_FIELDS)
        if needs_header:
            self._gate_csv_writer.writeheader()
            self._gate_csv.flush()

    def write_decision(self, row: Mapping[str, object]) -> None:
        payload = dict(row)
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
            self._gate_csv_writer.writerow(gate_row)
            self._gate_csv.flush()
        self._decisions.flush()

    def write_order_draft(self, row: Mapping[str, object]) -> None:
        self._drafts.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        self._drafts.flush()

    def write_attribution(self, row: Mapping[str, object]) -> None:
        self._attribution.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        self._attribution.flush()

    def write_near_miss(self, row: Mapping[str, object]) -> None:
        self._near_misses.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        self._near_misses.flush()

    def write_scout_decision(self, row: Mapping[str, object]) -> None:
        self._scout_decisions.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        self._scout_decisions.flush()

    def close(self) -> None:
        self._decisions.close()
        self._drafts.close()
        self._attribution.close()
        self._near_misses.close()
        self._scout_decisions.close()
        self._gate_rejections.close()
        self._gate_csv.close()

    def __enter__(self) -> "DecisionAuditWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
