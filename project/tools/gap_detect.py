"""Deteksi celah slider puzzle Shopee — warna + struktur.

Ground truth (dari analisis visual k2_puzzle_precise):
  - Gambar puzzle: 2 keranjang apel di meja abu-abu.
  - PIECE menonjol di KIRI (~2-8%).
  - CELAH (gap) = area abu-abu kosong di TENGAH (~40-50%).
  - CELAH = area warna "background" (abu) polos, menyatu dgn meja.

Metode:
  1. Sample warna bg (dari baris bawah gambar = meja abu).
  2. Tiap kolom: hitung % piksel mirip bg.
  3. Celah = kolom dgn % bg TINGGI (area kosong) di tengah (25-65%).
  4. Gap_x = pusat cluster kolom-bg-tinggi.
  5. Piece_x = tepi kiri gambar (potongan menonjol).
"""
import numpy as np


def detect_gap(png_path, debug=False):
    from PIL import Image
    im = Image.open(png_path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    h, w, _ = a.shape

    # --- sample warna background (meja) dari strip bawah ---
    bottom = a[int(h * 0.82):int(h * 0.97), :, :]
    bg = bottom.reshape(-1, 3).mean(axis=0)

    # --- % piksel mirip bg per kolom ---
    dist = np.linalg.norm(a - bg[None, None, :], axis=2)   # h x w
    sim = (dist < 55).astype(np.float32)                    # 1 kalau mirip bg
    col_bg = sim.mean(axis=0)                               # w

    # celah ada di tengah
    lo, hi = int(w * 0.22), int(w * 0.70)
    seg = col_bg[lo:hi]
    if len(seg) == 0:
        return None

    # cari cluster kolom dgn col_bg tertinggi (celah = banyak bg)
    thresh = seg.max() * 0.85
    cols = np.where(seg >= thresh)[0]
    gap_x = int(cols.mean()) + lo if len(cols) else int(np.argmax(seg)) + lo

    piece_x = int(w * 0.03)
    offset_img = max(0, gap_x - piece_x)

    out = {"gap_x": gap_x, "piece_x": piece_x, "offset_img": offset_img,
           "img_w": w, "img_h": h, "gap_pct": round(100 * gap_x / w, 1),
           "piece_pct": round(100 * piece_x / w, 1),
           "bg": [int(x) for x in bg], "max_col_bg": float(seg.max())}
    if debug:
        out["col_bg_sample"] = [round(float(x), 2) for x in col_bg[::max(1, w // 20)]]
    return out


def offset_to_screen(offset_img, img_w, display_w):
    if not img_w or not display_w:
        return offset_img
    return int(offset_img * (display_w / img_w))
