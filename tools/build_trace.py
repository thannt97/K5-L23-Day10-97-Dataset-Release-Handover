#!/usr/bin/env python3
"""Build Day 10 trace.json from a delivery's ticket, jobs and detection labels.

This uses the guideline recorded on the job, not the mutable per-image metadata.
It does not read ``_private`` or any original COCO annotation.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create trace.json for a Day 10 delivery")
    parser.add_argument("delivery", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    delivery = args.delivery
    changelog = (delivery / "guideline" / "changelog.md").read_text(encoding="utf-8")
    ticket = (delivery / "incoming" / "ticket.md").read_text(encoding="utf-8")
    changed = re.search(r"Lớp `([^`]+)`", changelog)
    if not changed:
        raise SystemExit("Không tìm thấy lớp đổi quy tắc trong guideline/changelog.md")
    target_class = changed.group(1)
    reported = set(re.findall(r"scene_\d+", ticket))
    if not reported:
        raise SystemExit("Không tìm thấy scene được báo trong incoming/ticket.md")
    classes = {}
    for line in (delivery / "classes.txt").read_text(encoding="utf-8").splitlines():
        index, name = line.split(" ", 1)
        classes[int(index)] = name.strip()
    with (delivery / "jobs.csv").open(encoding="utf-8", newline="") as handle:
        jobs = {row["job_id"]: row for row in csv.DictReader(handle)}
    metadata = json.loads((delivery / "metadata.json").read_text(encoding="utf-8"))["items"]
    tier_a, tier_b, job_ids = [], [], set()
    for item in metadata:
        job = jobs[item["job_id"]]
        # v1.2 is the old guideline in the Day 10 changelog. The comparison is
        # intentionally made through jobs.csv, not item['guideline_version'].
        if job["guideline"] != "v1.2":
            continue
        label = delivery / "labels" / f"{item['image']}.txt"
        names = {classes.get(int(float(line.split()[0]))) for line in label.read_text(encoding="utf-8").splitlines() if line.strip()}
        if target_class not in names:
            continue
        job_ids.add(job["job_id"])
        (tier_a if item["scene_id"] in reported else tier_b).append(item["image"])
    notify = sorted({jobs[job_id][role] for job_id in job_ids for role in ("annotator", "reviewer")})
    result = {"tier_a": sorted(tier_a), "tier_b": sorted(tier_b), "notify": notify}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"class={target_class}; tier_a={len(tier_a)}; tier_b={len(tier_b)}; notify={len(notify)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
