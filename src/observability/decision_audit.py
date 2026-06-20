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
        self._gate_rows: list[dict[str, object]] = []

    def write_decision(self, row: Mapping[str, object]) -> None:
        payload = dict(row)
        self._decisions.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        action = str(payload.get("action", ""))
        if action not in {"PROBE", "DIRECT"}:
            reasons = payload.get("reasons", [])
            reason_list = [str(item) for item in reasons] if isinstance(reasons, list) else [str(reasons)]
            self._gate_rows.append(
                {
                    "timestamp": payload.get("timestamp", ""),
                    "symbol": payload.get("symbol", ""),
                    "action": action,
                    "score": payload.get("score", ""),
                    "primary_reason": reason_list[0] if reason_list else "",
                    "reasons": "|".join(reason_list),
                }
            )

    def write_order_draft(self, row: Mapping[str, object]) -> None:
        self._drafts.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")

    def write_attribution(self, row: Mapping[str, object]) -> None:
        self._attribution.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")

    def close(self) -> None:
        self._decisions.close()
        self._drafts.close()
        self._attribution.close()
        with (self.output_dir / "gate_rejections.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=GATE_REJECTION_FIELDS)
            writer.writeheader()
            writer.writerows(self._gate_rows)

    def __enter__(self) -> "DecisionAuditWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
