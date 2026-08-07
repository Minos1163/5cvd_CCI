# -*- coding: utf-8 -*-
"""slice_klines.py — 按 open_time 裁剪 CSV K 线数据(用于短窗口完整链重放)。

用法: python scripts/slice_klines.py --src data/raw/binance_futures/atom_90d \
        --dst data/raw/binance_futures/atom_8d --start 2026-08-01T00:00:00Z
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--dst", required=True)
    parser.add_argument("--start", default="2026-08-01T00:00:00Z")
    args = parser.parse_args()

    import datetime as dt

    start_ts = int(dt.datetime.fromisoformat(args.start.replace("Z", "+00:00")).timestamp() * 1000)
    src = Path(args.src)
    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    for tf_dir in sorted(p for p in src.iterdir() if p.is_dir()):
        for csv_path in sorted(tf_dir.glob("*.csv")):
            rows_out = []
            with csv_path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    if int(row["open_time"]) >= start_ts:
                        rows_out.append(row)
            out_dir = dst / tf_dir.name
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / csv_path.name
            with out_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows_out)
            total_rows += len(rows_out)
            print(f"  {tf_dir.name}/{csv_path.name}: {len(rows_out)} rows")
    # 复制 manifest(更新说明)
    src_manifest = src / "manifest.json"
    if src_manifest.exists():
        import json

        m = json.loads(src_manifest.read_text(encoding="utf-8"))
        m["sliced_from"] = str(src_manifest)
        m["sliced_start"] = args.start
        (dst / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"RESULT: total_rows={total_rows} dst={dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
