#!/usr/bin/env python3
"""Convert a human TSV review sheet into the lab's review_log.csv format."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


TYPE_MAP = {"class_or_category_swap": "category_swap"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Import confirmed/rejected human review rows")
    parser.add_argument("source", type=Path, help="TSV with image_id, verdict, reason, candidate_type")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    with args.source.open(encoding="utf-8", newline="") as handle:
        source = list(csv.DictReader(handle, delimiter="\t"))
    rows = []
    for row in source:
        verdict = row["verdict"].strip()
        if verdict not in {"confirmed", "rejected"}:
            continue
        kind = TYPE_MAP.get(row["candidate_type"].strip(), row["candidate_type"].strip())
        rows.append({"image": row["image_id"].strip(), "type": kind, "verdict": verdict, "note": row["reason"].strip()})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "type", "verdict", "note"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.out}: {sum(row['verdict'] == 'confirmed' for row in rows)} confirmed, {sum(row['verdict'] == 'rejected' for row in rows)} rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
