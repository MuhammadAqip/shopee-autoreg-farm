"""Slider-puzzle solver Shopee — image-diff.

Alur:
  1. Tunggu canvas puzzle ter-render (#anti_fraud_captcha canvas, w>100).
  2. Ekstrak gambar puzzle (canvas.toDataURL) → PNG.
  3. Cari kolom CELAH (gap): potongan puzzle yang hilang tampak sbg kolom dgn
     varian/perbedaan menonjol — deteksi via gray-column std atau abs-diff
     antar kolom tetangga.
  4. Hitung offset = x celah - x awal gambar (piece start).
  5. Geser grip sejauh offset (human_drag dari ui_solver).
  6. SDK Shopee encrypt + POST verify otomatis.

Catatan: Shopee slider = gambar tunggal dgn celah (bukan 2 layer piece/bg).
Celah = area yg "kosong"/berbeda di dalam gambar. Strategi image-diff:
  - konversi grayscale
  - corr column: untuk tiap x, ukur variasi vertikal (celah = edge kuat)
  - cari puncak → x celah
"""
import base64
import io
import json
from pathlib import Path

SHOT = Path("/root/shopee-farm/shots")
SHOT.mkdir(parents=True, exist_ok=True)

JS_GET_PUZZLE = r"""
() => {
  const cont = document.querySelector('#anti_fraud_captcha') || document.body;
  const cv = [...cont.querySelectorAll('canvas')]
      .filter(c => c.getBoundingClientRect().width > 100 || c.width > 100);
  const out = {count: cv.length, imgs: [], rects: []};
  for (const c of cv) {
    const r = c.getBoundingClientRect();
    let url = '';
    try { url = c.toDataURL('image/png'); } catch(e) { url = ''; }
    if (url) out.imgs.push(url);
    out.rects.push({x:r.x, y:r.y, w:r.width, h:r.height, cw:c.width, ch:c.height});
  }
  // fallback: img puzzle
  if (!out.imgs.length) {
    const img = [...cont.querySelectorAll('img')]
        .filter(i => i.getBoundingClientRect().width > 100)[0];
    if (img) { out.imgs.push(img.src); out.rects.push({x:0,y:0,w:img.width,h:img.height}); }
  }
  return out;
}
"""


def grab_puzzle(page, save_prefix="puzzle"):
    data = page.evaluate(JS_GET_PUZZLE)
    saved = []
    for idx, url in enumerate(data.get("imgs", [])):
        if not url:
            continue
        raw = None
        if url.startswith("data:"):
            raw = base64.b64decode(url.split(",", 1)[1])
        else:
            import requests
            try:
                raw = requests.get(url, timeout=15).content
            except Exception:
                raw = None
        if raw:
            p = SHOT / f"{save_prefix}_{idx}.png"
            p.write_bytes(raw)
            saved.append(str(p))
    return {"count": data.get("count"), "rects": data.get("rects"), "saved": saved}


def find_gap_x(png_path):
    """Cari x celah via analisis kolom (numpy + PIL).

    Return (gap_x, img_w, score) — gap_x dlm piksel gambar.
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None
    im = Image.open(png_path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    h, w, _ = a.shape
    # celah puzzle biasanya: boundary tajam vertikal + area lebih terang/gelap
    gray = a.mean(axis=2)
    # gradien horizontal (edge vertikal)
    gx = np.abs(np.diff(gray, axis=1))
    col_edge = gx.mean(axis=0)  # panjang w-1
    # cari puncak di 20-100% dari kiri (celah gak di tepi)
    lo = int(w * 0.15)
    hi = int(w * 0.95)
    seg = col_edge[lo:hi]
    if len(seg) == 0:
        return None
    k = int(np.argmax(seg)) + lo
    # refine: ambil titik dgn edge terkuat (batas kiri celah)
    score = float(seg.max())
    return {"gap_x": k, "img_w": w, "score": score}


def estimate_offset(page, grip_rect, puzzle_rect, gap_x):
    """Konversi gap_x (piksel gambar) → jarak geser grip (piksel layar).

    Asumsi: gambar puzzle dirender 1:1 dgn skala tampilan.
    offset_screen = gap_x * (display_w / canvas_w)
    """
    if not gap_x or not puzzle_rect:
        return None
    disp_w = puzzle_rect.get("w") or puzzle_rect.get("cw")
    canvas_w = puzzle_rect.get("cw") or gap_x["img_w"]
    scale = disp_w / gap_x["img_w"] if gap_x.get("img_w") else 1.0
    return gap_x["gap_x"] * scale
