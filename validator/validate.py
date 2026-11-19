#!/usr/bin/env python3
"""Validate a Day 10 delivery without reading any data outside ``delivery``.

Usage:
    python validator/validate.py DELIVERY --out errors.json [--candidates candidates.json]

The errors output contains only rule-detectable faults.  Cross-source signals are
written separately as candidates because a human must inspect the image before a
semantic fault is reported.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pngutil  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jobs(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["job_id"]: row for row in csv.DictReader(handle)}


def read_classes(path: Path) -> dict[int, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            number, name = line.split(" ", 1)
            result[int(number)] = name.strip()
    return result


def read_labels(path: Path) -> list[tuple[int, float, float, float, float]]:
    boxes = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 5:
            raise ValueError(f"{path}:{line_number}: expected 5 columns")
        cls, x, y, w, h = map(float, parts[:5])
        boxes.append((int(cls), x, y, w, h))
    return boxes


def xyxy(box: tuple[int, float, float, float, float], width: int, height: int) -> tuple[float, float, float, float]:
    _, x, y, w, h = box
    return ((x - w / 2) * width, (y - h / 2) * height, (x + w / 2) * width, (y + h / 2) * height)


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, right - left) * max(0.0, bottom - top)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / (area_a + area_b - inter + 1e-9)


def pixel_stats(mask_path: Path, track_ids: set[int]) -> tuple[int, int, dict[int, dict]]:
    """Return area/bbox/pixels only for panoptic ids relevant to thing checks."""
    width, height, pixels = pngutil.read_rgb(mask_path)
    stats: dict[int, dict] = {}
    for offset in range(0, len(pixels), 3):
        segment_id = pngutil.segment_id(pixels, offset)
        if not segment_id or segment_id not in track_ids:
            continue
        pos = offset // 3
        x, y = pos % width, pos // width
        row = stats.setdefault(segment_id, {"area": 0, "left": x, "top": y, "right": x, "bottom": y, "pixels": []})
        row["area"] += 1
        row["left"] = min(row["left"], x)
        row["top"] = min(row["top"], y)
        row["right"] = max(row["right"], x)
        row["bottom"] = max(row["bottom"], y)
        row["pixels"].append(pos)
    return width, height, stats


def add(errors: set[tuple[str, str]], kind: str, target: str) -> None:
    errors.add((kind, target))


def rule_errors(delivery: Path) -> tuple[set[tuple[str, str]], list[dict]]:
    manifest = load_json(delivery / "manifest.json")["items"]
    metadata = {row["image"]: row for row in load_json(delivery / "metadata.json")["items"]}
    jobs = read_jobs(delivery / "jobs.csv")
    classes = read_classes(delivery / "classes.txt")
    panoptic = load_json(delivery / "panoptic.json")
    categories = {item["id"]: item for item in panoptic["categories"]}
    annotations = {item["image_id"]: item for item in panoptic["annotations"]}
    images = {Path(item["file_name"]).stem: item for item in panoptic["images"]}
    errors: set[tuple[str, str]] = set()
    candidates: list[dict] = []
    scenes: dict[str, set[str]] = defaultdict(set)

    for stem, item in manifest.items():
        meta = metadata.get(stem)
        if not meta:
            continue
        scenes[meta["scene_id"]].add(meta["split"])
        image_path = delivery / item["image"]
        label_path = delivery / item["label"]
        mask_path = delivery / item["mask"]
        if not image_path.is_file():
            add(errors, "missing_image", stem)
        elif sha256(image_path) != item.get("image_sha256"):
            add(errors, "wrong_hash", stem)
        job = jobs.get(meta["job_id"])
        if job and meta.get("guideline_version") != job.get("guideline"):
            add(errors, "guideline_mismatch", stem)

        try:
            boxes = read_labels(label_path)
        except (OSError, ValueError):
            boxes = []
        invalid = any(cls not in classes for cls, *_ in boxes)
        if invalid:
            add(errors, "invalid_class", stem)
        out_of_bounds = any(x - w / 2 < -0.01 or y - h / 2 < -0.01 or x + w / 2 > 1.01 or y + h / 2 > 1.01
                            for _, x, y, w, h in boxes)
        if out_of_bounds:
            add(errors, "bbox_out_of_bounds", stem)
        if duplicate_box(boxes, images.get(stem, {})):
            add(errors, "duplicate_box", stem)

        annotation = annotations.get(images.get(stem, {}).get("id"))
        if annotation:
            bad_category = any(segment["category_id"] not in categories for segment in annotation["segments_info"])
            if bad_category:
                add(errors, "invalid_category_id", stem)
            if mask_path.is_file():
                try:
                    tracked = {segment["id"] for segment in annotation["segments_info"]
                               if categories.get(segment["category_id"], {}).get("isthing")}
                    width, height, stats = pixel_stats(mask_path, tracked)
                    if any(segment["id"] in stats and segment.get("area") != stats[segment["id"]]["area"]
                           for segment in annotation["segments_info"]):
                        # A smaller actual area is the overlap signal; a different larger
                        # area alone can occur from serialisation/rounding and is not flagged.
                        if any(segment["id"] in stats and segment.get("area", 0) > stats[segment["id"]]["area"]
                               for segment in annotation["segments_info"]):
                            add(errors, "thing_overlap", stem)
                    candidates.extend(semantic_candidates(stem, boxes, annotation, categories, classes, width, height, stats))
                except (OSError, ValueError):
                    pass

    for scene, splits in scenes.items():
        if len(splits) > 1:
            add(errors, "scene_leak", scene)
    return errors, candidates


def duplicate_box(boxes: list[tuple[int, float, float, float, float]], image: dict) -> bool:
    width, height = image.get("width", 1), image.get("height", 1)
    for index, a in enumerate(boxes):
        for b in boxes[index + 1:]:
            if a[0] != b[0]:
                continue
            # Same dimensions plus a one/two-pixel centre offset: the injected fault.
            if abs(a[3] - b[3]) * width > 0.75 or abs(a[4] - b[4]) * height > 0.75:
                continue
            dx, dy = abs(a[1] - b[1]) * width, abs(a[2] - b[2]) * height
            if max(dx, dy) <= 2.5:
                return True
    return False


def semantic_candidates(stem: str, boxes: list[tuple[int, float, float, float, float]], annotation: dict,
                        categories: dict[int, dict], classes: dict[int, str], width: int, height: int,
                        stats: dict[int, dict]) -> list[dict]:
    """Produce conservative signals, never final semantic findings."""
    detections = [(box, classes.get(box[0]), xyxy(box, width, height)) for box in boxes if box[0] in classes]
    segments = []
    for segment in annotation["segments_info"]:
        category = categories.get(segment["category_id"])
        stat = stats.get(segment["id"])
        if not category or not category.get("isthing") or segment.get("iscrowd") or not stat:
            continue
        bbox = (stat["left"], stat["top"], stat["right"] + 1, stat["bottom"] + 1)
        segments.append((segment, category["name"], bbox, stat))
    out = []
    emitted: set[tuple[str, str]] = set()

    def emit(kind: str, detail: str) -> None:
        key = (kind, detail)
        if key not in emitted:
            emitted.add(key)
            out.append({"image": stem, "type": kind, "detail": detail})

    for box, name, rect in detections:
        overlaps = [(iou(rect, seg_rect), seg_name, seg_rect) for _, seg_name, seg_rect, _ in segments]
        if not overlaps:
            continue
        score, other_name, _ = max(overlaps)
        if score >= 0.35 and name != other_name:
            emit("class_or_category_swap", f"detection={name}; panoptic={other_name}; bbox_iou={score:.2f}")
        same = [score for score, seg_name, _ in overlaps if seg_name == name]
        if same and 0.05 <= max(same) < 0.45:
            emit("bbox_drift", f"class={name}; best_same_class_iou={max(same):.2f}")

    for _, seg_name, seg_rect, stat in segments:
        if stat["area"] < 1024:
            continue
        same = [(rect, iou(rect, seg_rect)) for _, name, rect in detections if name == seg_name]
        if not same or max(score for _, score in same) < 0.20:
            emit("missing_box", f"panoptic={seg_name}; area={stat['area']}")
        # A segment substantially covered by two same-class detection boxes is a
        # stronger merge signal than bbox overlap alone.
        nearby = [(rect, iou(rect, seg_rect)) for _, name, rect in detections if name == seg_name and iou(rect, seg_rect) >= 0.01]
        if len(nearby) < 2:
            continue
        coverages = []
        for rect, _ in nearby:
            hits = sum(rect[0] <= pos % width < rect[2] and rect[1] <= pos // width < rect[3] for pos in stat["pixels"])
            coverage = hits / stat["area"]
            if coverage >= 0.35:
                coverages.append((rect, coverage))
        pairs = [(a, b) for index, a in enumerate(coverages) for b in coverages[index + 1:]
                 if iou(a[0], b[0]) <= 0.20 and a[1] + b[1] >= 0.75]
        if pairs:
            _, first, second = max(((a[1] + b[1], a[1], b[1]) for a, b in pairs), key=lambda row: row[0])
            emit("instance_merge", f"panoptic={seg_name}; separate_box_coverage={first + second:.2f}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Day 10 delivery")
    parser.add_argument("delivery", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--candidates", type=Path)
    args = parser.parse_args()
    errors, candidates = rule_errors(args.delivery)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"errors": [{"type": kind, "target": target} for kind, target in sorted(errors)]}, indent=2) + "\n", encoding="utf-8")
    if args.candidates:
        args.candidates.parent.mkdir(parents=True, exist_ok=True)
        args.candidates.write_text(json.dumps({"candidates": candidates}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(errors)} rule errors" + (f"; {len(candidates)} review candidates" if args.candidates else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
