#!/usr/bin/env python3
"""Build a detection v2 handover from confirmed findings, without changing v1."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path


DET_REWORK = {"missing_image", "invalid_class", "bbox_out_of_bounds", "duplicate_box", "class_swap", "bbox_drift", "missing_box"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Day 10 detection handover v2")
    parser.add_argument("run", type=Path, help="e.g. runs/r3007")
    args = parser.parse_args()
    run, delivery = args.run, args.run / "delivery"
    release_id = json.loads((delivery / "release.json").read_text(encoding="utf-8"))["release_id"]
    errors = json.loads((run / "errors.json").read_text(encoding="utf-8"))["errors"]
    manifest = json.loads((delivery / "manifest.json").read_text(encoding="utf-8"))["items"]
    metadata = {row["image"]: row for row in json.loads((delivery / "metadata.json").read_text(encoding="utf-8"))["items"]}
    jobs = {row["job_id"]: row for row in read_csv(delivery / "jobs.csv")}
    names = {int(line.split(" ", 1)[0]): line.split(" ", 1)[1].strip() for line in (delivery / "classes.txt").read_text(encoding="utf-8").splitlines()}
    errors_by_image: dict[str, list[str]] = defaultdict(list)
    for error in errors:
        if error["target"] in manifest:
            errors_by_image[error["target"]].append(error["type"])
    rework = {stem for stem, kinds in errors_by_image.items() if set(kinds) & DET_REWORK}
    out = run / "handover" / f"{release_id}_v2"
    if out.exists():
        shutil.rmtree(out)
    (out / "images").mkdir(parents=True)
    (out / "labels").mkdir()
    kept = sorted(stem for stem in manifest if stem not in rework and (delivery / manifest[stem]["image"]).is_file())
    for stem in kept:
        shutil.copyfile(delivery / manifest[stem]["image"], out / "images" / f"{stem}.jpg")
        shutil.copyfile(delivery / manifest[stem]["label"], out / "labels" / f"{stem}.txt")

    with (out / "rework_queue.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "type", "annotator", "reviewer", "action"])
        writer.writeheader()
        for stem in sorted(rework):
            job = jobs[metadata[stem]["job_id"]]
            writer.writerow({"image": stem, "type": ";".join(sorted(errors_by_image[stem])), "annotator": job["annotator"],
                             "reviewer": job["reviewer"], "action": "reannotate_detection"})

    with (out / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "sha256"])
        writer.writeheader()
        for folder in ("images", "labels"):
            for path in sorted((out / folder).iterdir()):
                writer.writerow({"file": f"{folder}/{path.name}", "sha256": digest(path)})

    counts = Counter()
    for stem in kept:
        for line in (out / "labels" / f"{stem}.txt").read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[names[int(float(line.split()[0]))]] += 1
    with (out / "label_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["class", "count"])
        writer.writeheader()
        for name in sorted(counts):
            writer.writerow({"class": name, "count": counts[name]})
        writer.writerow({"class": "TOTAL", "count": sum(counts.values())})

    # Move an entire affected scene to its majority split, rather than trusting
    # the corrupted split of the one leaked image.
    split_by_scene: dict[str, list[str]] = defaultdict(list)
    for stem in kept:
        split_by_scene[metadata[stem]["scene_id"]].append(metadata[stem]["split"])
    corrected_split = {scene: Counter(splits).most_common(1)[0][0] for scene, splits in split_by_scene.items()}
    with (out / "truyvet.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "scene_id", "split", "job_id", "annotator", "reviewer", "guideline"])
        writer.writeheader()
        for stem in kept:
            meta, job = metadata[stem], jobs[metadata[stem]["job_id"]]
            writer.writerow({"image": stem, "scene_id": meta["scene_id"], "split": corrected_split[meta["scene_id"]],
                             "job_id": meta["job_id"], "annotator": job["annotator"], "reviewer": job["reviewer"], "guideline": job["guideline"]})

    guideline_groups = defaultdict(list)
    for job in jobs.values():
        guideline_groups[job["guideline"]].append(job["job_id"])
    total_v1, findings = len(manifest), len({row["target"] for row in errors})
    panoptic_only = sorted(stem for stem, kinds in errors_by_image.items() if stem not in rework and set(kinds) - {"wrong_hash", "guideline_mismatch", "scene_leak"})
    lines = [f"Release: {release_id}_v2", f"Parent: {release_id}", f"Số ảnh: {len(kept)}", f"Số nhãn: {sum(counts.values())}",
             "Guideline: " + "; ".join(f"{version} ({','.join(sorted(ids))})" for version, ids in sorted(guideline_groups.items())),
             f"QC v1: {findings}/{total_v1} = {findings / total_v1:.1%}",
             "Kết luận v1: Hold — vượt ngưỡng 2% ảnh/cảnh có lỗi đã xác minh.",
             "Kết luận v2: Hold — đã tách ảnh lỗi detection, sửa hash/guideline/split trong metadata bàn giao; chờ review lỗi ngữ nghĩa.",
             "Ghi chú: wrong_hash được thay bằng SHA-256 của bytes ảnh hiện có; guideline lấy theo jobs.csv; split scene dùng đa số của cảnh. "
             f"Rework giao lại cho annotator/reviewer của {len(rework)} ảnh. Ảnh lỗi panoptic vẫn ở v2: {', '.join(panoptic_only) or 'không có'}."]
    (out / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}: kept={len(kept)}, rework={len(rework)}, labels={sum(counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
