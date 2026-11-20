#!/usr/bin/env python3
"""Tính tín hiệu số từ mask cho từng ứng viên (KHÔNG xem ảnh, KHÔNG kết luận).

    py tools/review_signals.py delivery submission/de_an/review/TV1_Than.csv

instance_merge : số mảnh rời (8-liên thông, mảnh >= 5% segment) và % pixel segment nằm trong từng box cùng lớp.
missing_box    : diện tích segment (% ảnh), crowd, IoU tốt nhất với box cùng lớp.
bbox_drift     : % pixel segment nằm ngoài box cùng lớp phủ nhiều nhất.
class/category swap: máy không phân xử được -> phải nhìn vật.
"""
from __future__ import annotations
import argparse, csv, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pngutil  # noqa: E402


def boxes_of(lab: Path, classes, w, h):
    out = []
    if lab.is_file():
        for line in lab.read_text(encoding="utf-8").split("\n"):
            p = line.split()
            if len(p) == 5:
                c, x, y, bw, bh = int(p[0]), *map(float, p[1:])
                out.append((classes.get(c), (x - bw / 2) * w, (y - bh / 2) * h, (x + bw / 2) * w, (y + bh / 2) * h))
    return out


def components(pix: set[int], w: int) -> list[int]:
    seen, sizes = set(), []
    for start in pix:
        if start in seen:
            continue
        stack, n = [start], 0
        seen.add(start)
        while stack:
            p = stack.pop(); n += 1
            x, y = p % w, p // w
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (y + dy) * w + (x + dx)
                    if 0 <= x + dx < w and q in pix and q not in seen:
                        seen.add(q); stack.append(q)
        sizes.append(n)
    return sorted(sizes, reverse=True)


def inside(pix, w, b):
    return sum(b[1] <= p % w < b[3] and b[2] <= p // w < b[4] for p in pix)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u else 0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("delivery", type=Path); ap.add_argument("queue", type=Path); a = ap.parse_args()
    d = a.delivery
    classes = {int(n): s.strip() for n, s in (l.split(" ", 1) for l in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if l.strip())}
    pan = json.loads((d / "panoptic.json").read_text(encoding="utf-8"))
    cats = {c["id"]: c for c in pan["categories"]}
    imgs = {Path(i["file_name"]).stem: i for i in pan["images"]}
    anns = {x["image_id"]: x for x in pan["annotations"]}
    rows = list(csv.DictReader(a.queue.open(encoding="utf-8-sig")))
    cache = {}
    for r in rows:
        stem, kind = r["image"], r["type"]
        im = imgs[stem]; ann = anns[im["id"]]
        if stem not in cache:
            w, h, px = pngutil.read_rgb(d / "masks" / Path(ann["file_name"]).name)
            by = {}
            for i in range(w * h):
                sid = px[3 * i] + 256 * px[3 * i + 1] + 65536 * px[3 * i + 2]
                if sid:
                    by.setdefault(sid, set()).add(i)
            cache[stem] = (w, h, by, boxes_of(d / "labels" / f"{stem}.txt", classes, w, h))
        w, h, by, boxes = cache[stem]
        names = set(m.strip() for m in re.findall(r"(?:detection|panoptic|class)=([^;]+)", r["detail"]))
        segs = [s for s in ann["segments_info"] if cats.get(s["category_id"], {}).get("name") in names]
        msg = []
        if "swap" in kind:
            msg.append("máy không phân xử: nhìn vật thật là " + " hay ".join(sorted(names)))
        for s in segs:
            nm = cats[s["category_id"]]["name"]; pix = by.get(s["id"], set())
            if not pix:
                continue
            same = [b for b in boxes if b[0] == nm]
            area = len(pix)
            xs = [p % w for p in pix]; ys = [p // w for p in pix]
            sb = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
            tag = f"[{nm} seg#{s['id']}{' crowd' if s.get('iscrowd') else ''}, {100*area/(w*h):.1f}% ảnh]"
            if kind == "instance_merge":
                comp = [c for c in components(pix, w) if c >= 0.05 * area]
                cov = sorted((round(100 * inside(pix, w, b) / area) for b in same), reverse=True)[:3]
                msg.append(f"{tag} {len(comp)} mảnh rời lớn; box cùng lớp phủ {cov}%")
            elif kind == "missing_box":
                best = max((iou(sb, b[1:]) for b in same), default=0)
                msg.append(f"{tag} IoU tốt nhất với box {nm}: {best:.2f} ({len(same)} box {nm})")
            elif kind == "bbox_drift":
                best = max((inside(pix, w, b) for b in same), default=0)
                msg.append(f"{tag} {100*(area-best)/area:.0f}% pixel nằm ngoài box {nm} gần nhất")
        print(f"{stem} | {kind} | " + " ; ".join(msg))


if __name__ == "__main__":
    main()
