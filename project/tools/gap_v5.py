"""Gap detection v5 — cari CELAH = area GELAP (dark silhouette).

Insight vision (so_85729884045_puz0): piece flush di KIRI (x~0), celah =
area GELAP (hole silhouette) di tengah (~40-45%). Celah lebih gelap dari sekitarnya.

Metode:
  1. Dark mask: piksel jauh lebih gelap dari rata-rata lokal.
  2. Cari cluster gelap terbesar di tengah -> hole center.
  3. piece_x ~ 0 (kiri). offset = hole_x.
"""
import numpy as np
from PIL import Image


def detect(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(float)
    h, w, _ = a.shape
    gray = a.mean(2)

    # --- dark mask: piksel < (median - 1.2*std) ---
    med = np.median(gray); sd = gray.std()
    dark = (gray < med - 0.9 * sd).astype(float)

    # --- profil kolom: jumlah piksel gelap per kolom ---
    col_dark = dark.mean(axis=0)          # w
    # cari cluster di tengah (15%-70%)
    lo, hi = int(w * 0.15), int(w * 0.72)
    seg = col_dark[lo:hi]
    if len(seg) == 0:
        return None
    # ambil puncak; hole = area dgn dark tertinggi
    peak = int(np.argmax(seg)) + lo
    # perluas ke sekitar peak (cluster)
    thr = seg.max() * 0.6
    cols = np.where(seg >= thr)[0] + lo
    hole_x = int(cols.mean()) if len(cols) else peak

    piece_x = 0
    out = {"W": w, "H": h, "hole_x": hole_x, "piece_x": piece_x,
           "hole_pct": round(100 * hole_x / w, 1),
           "peak_dark": round(float(seg.max()), 3),
           "med": round(float(med), 1), "sd": round(float(sd), 1),
           "offset": max(0, hole_x - piece_x)}
    return out


if __name__ == "__main__":
    import sys
    for f in sys.argv[1:] or ["shots/so_85729884045_puz0.png"]:
        print(f, "->", detect(f))
