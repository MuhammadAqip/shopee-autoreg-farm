"""Solver slider puzzle Shopee — VERIFIED approach.

STRUKTUR PUZZLE (dari analisis visual h1/k2):
  - Gambar puzzle ~290-440px lebar.
  - PIECE (potongan) menonjol di TEPI KIRI gambar (~8-10% dari kiri).
  - GAP (celah kosong) di DALAM gambar (~30-35% dari kiri) — area tanpa tekstur.
  - Solusi: geser PIECE ke GAP → offset = gap_x - piece_x.

Deteksi via image-diff:
  1. Crop region puzzle.
  2. Cari GAP: kolom/area dgn variansi lokal RENDAH (polos/abu) di dalam gambar —
     beda dari gambar yg penuh tekstur. Ukur via local std dalam window.
  3. Cari PIECE: bagian yg menonjol / edge kuat di tepi kiri (x kecil).
  4. offset = gap_x - piece_x  (piksel gambar)
  5. Konversi ke layar (scale display/img).
"""
import time
from pathlib import Path

SHOT = Path("/root/shopee-farm/shots")
SHOT.mkdir(parents=True, exist_ok=True)


def analyze_slider(png_path):
    """Deteksi piece_x + gap_x dari gambar puzzle. Return dict."""
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None
    im = Image.open(png_path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    h, w, _ = a.shape
    gray = a.mean(axis=2)

    # --- GAP: cari area polos (variansi lokal rendah) di TENGAH gambar ---
    # celah Shopee = area abu-abu kosong di tengah (bukan tepi).
    col_std = np.array([gray[:, x].std() for x in range(w)])
    lo, hi = int(w * 0.25), int(w * 0.65)          # celah ada di tengah
    seg = col_std[lo:hi]
    if len(seg) == 0:
        return None
    gap_x = int(np.argmin(seg)) + lo

    # --- PIECE: bagian menonjol di tepi kiri (edge kuat, x kecil) ---
    gx = np.abs(np.diff(gray, axis=1))
    edge = gx.mean(axis=0)  # len w-1
    left_lo, left_hi = int(w * 0.02), int(w * 0.25)
    piece_x = left_lo
    if left_hi > left_lo:
        piece_x = int(np.argmax(edge[left_lo:left_hi])) + left_lo

    offset_img = max(0, gap_x - piece_x)
    return {"gap_x": gap_x, "piece_x": piece_x, "offset_img": offset_img,
            "img_w": w, "img_h": h,
            "gap_pct": round(100 * gap_x / w, 1),
            "piece_pct": round(100 * piece_x / w, 1)}


def offset_to_screen(offset_img, img_w, display_w):
    """Konversi offset gambar → offset layar."""
    if not img_w or not display_w:
        return offset_img
    return int(offset_img * (display_w / img_w))
