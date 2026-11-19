#!/usr/bin/env python3
"""Create a local HTML reviewer for candidates produced by validator/validate.py.

The reviewer is deliberately read-only: it helps a person inspect an image, but
does not decide a verdict or write ``review_log.csv``.

Example:
    python tools/review_candidates.py runs/r3007/delivery runs/r3007/candidates.json \
        --out runs/r3007/review.html
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from pathlib import Path


def yolo_boxes(path: Path, classes: dict[int, str], width: int, height: int) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cls, x, y, w, h = line.split()[:5]
        cls, x, y, w, h = int(float(cls)), float(x), float(y), float(w), float(h)
        out.append({"name": classes.get(cls, str(cls)), "x": (x - w / 2) * width,
                    "y": (y - h / 2) * height, "w": w * width, "h": h * height})
    return out


def focus_names(candidate: dict) -> set[str]:
    detail = candidate.get("detail", "")
    if candidate["type"] == "class_or_category_swap":
        return set(re.findall(r"(?:detection|panoptic)=([^;]+)", detail))
    match = re.search(r"(?:class|panoptic)=([^;]+)", detail)
    return {match.group(1)} if match else set()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an offline candidate review page")
    parser.add_argument("delivery", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    delivery = args.delivery.resolve()
    classes = {}
    for line in (delivery / "classes.txt").read_text(encoding="utf-8").splitlines():
        number, name = line.split(" ", 1)
        classes[int(number)] = name.strip()
    panoptic = json.loads((delivery / "panoptic.json").read_text(encoding="utf-8"))
    categories = {row["id"]: row for row in panoptic["categories"]}
    images = {Path(row["file_name"]).stem: row for row in panoptic["images"]}
    annotations = {row["image_id"]: row for row in panoptic["annotations"]}
    raw_candidates = json.loads(args.candidates.read_text(encoding="utf-8"))["candidates"]
    rows = []
    for candidate in raw_candidates:
        stem = candidate["image"]
        image = images[stem]
        names = focus_names(candidate)
        segments = []
        for segment in annotations[image["id"]]["segments_info"]:
            category = categories.get(segment["category_id"], {})
            if category.get("name") in names:
                x, y, w, h = segment["bbox"]
                segments.append({"name": category["name"], "x": x, "y": y, "w": w, "h": h})
        image_file = delivery / "images" / image["file_name"]
        rows.append({"candidate": candidate, "boxes": yolo_boxes(delivery / "labels" / f"{stem}.txt", classes, image["width"], image["height"]),
                     "segments": segments, "focus": sorted(names), "width": image["width"], "height": image["height"],
                     "image": Path(os.path.relpath(image_file, args.out.parent.resolve())).as_posix()})
    payload = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(f"Review candidates — {args.candidates}")
    document = f"""<!doctype html>
<meta charset="utf-8"><title>{title}</title>
<style>body{{font:16px system-ui;margin:24px;max-width:1100px}} canvas{{max-width:100%;border:1px solid #aaa;display:block}} button{{padding:7px 12px;margin-right:8px}} #detail{{white-space:pre-wrap;margin:14px 0}} .warn{{color:#9b1c1c}}</style>
<h1>{title}</h1><p class="warn">Đây là công cụ xem ảnh, không tự kết luận lỗi. Chỉ ghi <code>confirmed</code> sau khi người review quan sát ảnh.</p>
<button onclick="move(-1)">← Trước</button><button onclick="move(1)">Sau →</button><span id="position"></span><div id="detail"></div><canvas id="canvas"></canvas>
<script>const rows={payload}; let index=0, image=new Image(), canvas=document.getElementById('canvas'), ctx=canvas.getContext('2d');
function move(n){{index=(index+n+rows.length)%rows.length; render();}}
function rect(x,y,w,h,color,text){{ctx.strokeStyle=color;ctx.lineWidth=3;ctx.strokeRect(x,y,w,h);ctx.fillStyle=color;ctx.fillText(text,x+3,Math.max(14,y-4));}}
function render(){{let r=rows[index]; document.getElementById('position').textContent=` ${{index+1}} / ${{rows.length}}`;document.getElementById('detail').textContent=`${{r.candidate.image}} · ${{r.candidate.type}}\n${{r.candidate.detail}}\nFocus: ${{r.focus.join(', ') || 'n/a'}}\nĐỏ = detection; xanh = panoptic bbox.`;image.onload=()=>{{canvas.width=r.width;canvas.height=r.height;ctx.drawImage(image,0,0);r.boxes.forEach(b=>rect(b.x,b.y,b.w,b.h,r.focus.includes(b.name)?'#dc2626':'#ef9a9a',b.name));r.segments.forEach(s=>rect(s.x,s.y,s.w,s.h,'#047857','panoptic '+s.name));}};image.src=r.image;}} render();</script>"""
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(document, encoding="utf-8")
    print(f"wrote {args.out}: {len(rows)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
