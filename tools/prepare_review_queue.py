#!/usr/bin/env python3
"""Turn validator candidates into a blank, human-owned review queue.

No verdict is inferred or written: a reviewer must fill verdict and note after
opening the image in review.html (or another image viewer).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ORDER = {"class_or_category_swap": 0, "bbox_drift": 1, "missing_box": 2, "instance_merge": 3}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a blank review queue")
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))["candidates"]
    candidates.sort(key=lambda row: (ORDER.get(row["type"], 99), row["image"], row["detail"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "type", "detail", "reviewer", "verdict", "note"])
        writer.writeheader()
        for row in candidates:
            writer.writerow({"image": row["image"], "type": row["type"], "detail": row["detail"],
                             "reviewer": "", "verdict": "", "note": ""})
    print(f"wrote {args.out}: {len(candidates)} unreviewed candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
