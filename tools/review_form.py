#!/usr/bin/env python3
"""Tạo trang HTML để MỘT người review hàng đợi của mình (công cụ xem ảnh, không tự kết luận).

    py tools/review_form.py delivery submission/de_an/review/TV2_Tuan.csv --out delivery/review_TV2.html

- Ảnh và mask được nhúng base64 (mở bằng file:// vẫn đọc được pixel mask).
- Xanh lá: pixel của segment panoptic liên quan; đỏ: box detection cùng lớp; hồng: box lớp khác.
- Người review bấm confirmed/rejected, ghi note, chọn class_swap/category_swap cho ca đổi lớp,
  rồi bấm "Tải CSV" và chép đè vào file csv hàng đợi của mình.
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import re
from pathlib import Path


def b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def focus_names(detail: str) -> set[str]:
    return {m.strip() for m in re.findall(r"(?:detection|panoptic|class)=([^;]+)", detail)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Form review cho một người")
    ap.add_argument("delivery", type=Path)
    ap.add_argument("queue", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    d = a.delivery
    classes = {int(n): s.strip() for n, s in (l.split(" ", 1) for l in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if l.strip())}
    pan = json.loads((d / "panoptic.json").read_text(encoding="utf-8"))
    cats = {c["id"]: c for c in pan["categories"]}
    imgs = {Path(i["file_name"]).stem: i for i in pan["images"]}
    anns = {x["image_id"]: x for x in pan["annotations"]}
    with a.queue.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    media, items = {}, []
    for r in rows:
        stem = r["image"]
        im = imgs[stem]
        w, h = im["width"], im["height"]
        jpg = d / "images" / im["file_name"]
        ann = anns[im["id"]]
        mask = d / "masks" / Path(ann["file_name"]).name
        if stem not in media:
            media[stem] = {"img": b64(jpg, "image/jpeg") if jpg.is_file() else "", "mask": b64(mask, "image/png") if mask.is_file() else ""}
        names = focus_names(r.get("detail", ""))
        segs = [{"id": s["id"], "name": cats.get(s["category_id"], {}).get("name", "?"), "bbox": s["bbox"], "crowd": s.get("iscrowd", 0)}
                for s in ann["segments_info"] if cats.get(s["category_id"], {}).get("name") in names]
        boxes = []
        lab = d / "labels" / f"{stem}.txt"
        if lab.is_file():
            for line in lab.read_text(encoding="utf-8").split("\n"):
                p = line.split()
                if len(p) != 5:
                    continue
                c, x, y, bw, bh = int(p[0]), *map(float, p[1:])
                boxes.append({"name": classes.get(c, f"id{c}"), "x": (x - bw / 2) * w, "y": (y - bh / 2) * h, "w": bw * w, "h": bh * h})
        items.append({**r, "w": w, "h": h, "segs": segs, "boxes": boxes, "focus": sorted(names), "has_img": bool(media[stem]["img"])})
    payload = json.dumps({"items": items, "media": media, "file": a.queue.name}, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(f"Review — {a.queue.name}")
    doc = """<!doctype html><meta charset="utf-8"><title>TITLE</title>
<style>
body{font:15px system-ui;margin:16px;background:#fafafa}#top{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.wrap{display:flex;gap:12px;margin-top:10px;flex-wrap:wrap}canvas{border:1px solid #999;background:#fff;max-width:100%}
#full{max-width:560px}#zoom{max-width:560px}button{padding:6px 12px}#info{white-space:pre-wrap;background:#fff;border:1px solid #ddd;padding:8px;margin-top:8px}
.ok{background:#16a34a;color:#fff}.no{background:#dc2626;color:#fff}textarea{width:100%;height:60px}.warn{color:#9b1c1c}
#list span{display:inline-block;width:14px;height:14px;margin:1px;border-radius:3px;background:#ccc;cursor:pointer}
</style>
<h2>TITLE</h2><p class="warn">Công cụ chỉ hiển thị. Người review tự nhìn ảnh rồi mới chọn. Note phải nói THẤY GÌ (≥ 20 ký tự).</p>
<div id="top"><button onclick="go(-1)">← Trước (A)</button><button onclick="go(1)">Sau → (D)</button><b id="pos"></b>
<label><input type="checkbox" id="showAll" onchange="draw()"> hiện mọi box</label>
<label>Zoom lề <input type="range" id="pad" min="0" max="200" value="40" oninput="draw()"></label>
<button onclick="dl()">⬇ Tải CSV</button></div>
<div id="list"></div><div id="info"></div>
<div class="wrap"><canvas id="full"></canvas><canvas id="zoom"></canvas></div>
<p>Loại: <select id="type"></select>
<button class="ok" onclick="setV('confirmed')">confirmed (C)</button> <button class="no" onclick="setV('rejected')">rejected (R)</button> <b id="v"></b></p>
<textarea id="note" placeholder="Thấy gì trong ảnh, ví dụ: hai người đứng tách nhau nhưng mask gộp thành một segment person" oninput="cur().note=this.value;mark()"></textarea>
<script>
const D=PAYLOAD;let i=0;const cache={};
const TYPES={class_or_category_swap:["class_or_category_swap","class_swap","category_swap"]};
function cur(){return D.items[i]}
function load(src){return new Promise(r=>{if(!src)return r(null);const im=new Image();im.onload=()=>r(im);im.src=src;})}
async function media(stem){if(!cache[stem]){const m=D.media[stem];cache[stem]={img:await load(m.img),mask:await load(m.mask)}}return cache[stem]}
function mark(){document.getElementById('list').innerHTML=D.items.map((r,k)=>`<span title="${r.image} ${r.type}" style="background:${r.verdict=='confirmed'?'#16a34a':r.verdict=='rejected'?'#dc2626':'#ccc'};outline:${k==i?'2px solid #000':'none'}" onclick="i=${k};draw()"></span>`).join('');
 const r=cur();document.getElementById('v').textContent=r.verdict||'(chưa xem)';}
async function draw(){const r=cur();const m=await media(r.image);const W=r.w,H=r.h;
 document.getElementById('pos').textContent=` ${i+1}/${D.items.length}`;
 document.getElementById('info').textContent=`${r.image} · ${r.type}\n${r.detail}\nSegment liên quan: ${r.segs.map(s=>s.name+(s.crowd?' (crowd)':'')).join(', ')||'—'}  |  Box: ${r.boxes.filter(b=>r.focus.includes(b.name)).length} box lớp ${r.focus.join('/')}${r.has_img?'':'\\n⚠ KHÔNG có file ảnh'}`;
 const sel=document.getElementById('type');const opts=TYPES[r.type.replace(/^(class_swap|category_swap)$/,'class_or_category_swap')]||[r.type];
 sel.innerHTML=opts.map(t=>`<option ${t==r.type?'selected':''}>${t}</option>`).join('');sel.onchange=()=>{r.type=sel.value;};
 document.getElementById('note').value=r.note||'';mark();
 const c=document.getElementById('full');c.width=W;c.height=H;const x=c.getContext('2d');
 if(m.img)x.drawImage(m.img,0,0,W,H);
 if(m.mask){const t=document.createElement('canvas');t.width=W;t.height=H;const tx=t.getContext('2d');tx.drawImage(m.mask,0,0);
  const md=tx.getImageData(0,0,W,H).data,ov=x.getImageData(0,0,W,H),od=ov.data,ids=new Set(r.segs.map(s=>s.id));
  for(let p=0;p<W*H;p++){const id=md[4*p]+256*md[4*p+1]+65536*md[4*p+2];if(ids.has(id)){od[4*p]=od[4*p]*.45;od[4*p+1]=od[4*p+1]*.45+140;od[4*p+2]=od[4*p+2]*.45;}}
  x.putImageData(ov,0,0);}
 x.font='bold 13px system-ui';x.lineWidth=2;
 const all=document.getElementById('showAll').checked;
 for(const b of r.boxes){const f=r.focus.includes(b.name);if(!f&&!all)continue;x.strokeStyle=f?'#dc2626':'#f9a8d4';x.strokeRect(b.x,b.y,b.w,b.h);x.fillStyle=x.strokeStyle;x.fillText(b.name,b.x+2,Math.max(12,b.y-3));}
 for(const s of r.segs){const[a,b2,w,h]=s.bbox;x.setLineDash([5,4]);x.strokeStyle='#047857';x.strokeRect(a,b2,w,h);x.setLineDash([]);x.fillStyle='#047857';x.fillText('pan:'+s.name,a+2,b2+h+13>H?b2+h-3:b2+h+13);}
 const pad=+document.getElementById('pad').value;let rs=[...r.segs.map(s=>s.bbox),...r.boxes.filter(b=>r.focus.includes(b.name)).map(b=>[b.x,b.y,b.w,b.h])];
 if(!rs.length)rs=[[0,0,W,H]];let x0=Math.max(0,Math.min(...rs.map(q=>q[0]))-pad),y0=Math.max(0,Math.min(...rs.map(q=>q[1]))-pad),
 x1=Math.min(W,Math.max(...rs.map(q=>q[0]+q[2]))+pad),y1=Math.min(H,Math.max(...rs.map(q=>q[1]+q[3]))+pad);
 const z=document.getElementById('zoom'),s=Math.min(560/(x1-x0),560/(y1-y0),6);z.width=(x1-x0)*s;z.height=(y1-y0)*s;const zx=z.getContext('2d');zx.imageSmoothingEnabled=false;zx.drawImage(c,x0,y0,x1-x0,y1-y0,0,0,z.width,z.height);}
function go(n){i=(i+n+D.items.length)%D.items.length;draw()}
function setV(v){const r=cur();if(v==='confirmed'&&r.type==='class_or_category_swap'){alert('Chọn class_swap hoặc category_swap trước khi confirmed');return}r.verdict=v;mark();}
function dl(){const miss=D.items.filter(r=>!r.verdict||(r.note||'').trim().length<20);if(miss.length&&!confirm(miss.length+' dòng chưa có verdict hoặc note < 20 ký tự. Vẫn tải?'))return;
 const q=s=>'"'+String(s??'').replace(/"/g,'""')+'"';const cols=['image','type','detail','reviewer','verdict','note'];
 const t='\\ufeff'+cols.join(',')+'\\r\\n'+D.items.map(r=>cols.map(k=>q(r[k])).join(',')).join('\\r\\n')+'\\r\\n';
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([t],{type:'text/csv'}));a.download=D.file;a.click();}
document.addEventListener('keydown',e=>{if(e.target.tagName==='TEXTAREA')return;if(e.key==='a')go(-1);if(e.key==='d')go(1);if(e.key==='c')setV('confirmed');if(e.key==='r')setV('rejected');});
draw();
</script>"""
    doc = doc.replace("TITLE", title).replace("PAYLOAD", payload)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(doc, encoding="utf-8")
    print(f"wrote {a.out}: {len(items)} ứng viên, {len(media)} ảnh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
