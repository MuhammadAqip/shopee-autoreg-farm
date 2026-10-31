"""Gap detection v6 — TEMPLATE-MATCH hole-shape.

Ide: shape puzzle-piece (bentuk knob/tab) konstan di SEMUA puzzle Shopee.
Piece di kiri (x~0). Celah (hole) = area yg HILANG dari gambar background.

Metode template-match:
  1. Ambil template = PIECE (bentuk puzzle di kiri, x~0..~44).
  2. Slide template di sepanjang gambar (matchTemplate TM_CCOEFF_NORMED),
     cari lokasi TERBAIK selain posisi piece asli.
  3. Lokasi terbaik = hole (celah kosong bentuknya sama).
  4. offset = hole_x - piece_x.
"""
import cv2
import numpy as np


def detect(path):
    img = cv2.imread(path)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    out = {"W": w, "H": h}

    # piece di kiri ~ x 0..44 (dari rect grip 44px)
    pw = max(20, int(w * 0.16))
    piece = gray[:, 0:pw]
    piece_x = 0

    # slide piece di gambar (mulai dari 20% biar gak match diri sendiri)
    res = cv2.matchTemplate(gray, piece, cv2.TM_CCOEFF_NORMED)
    res = res.ravel()
    start = int(w * 0.20)
    seg = res[start:]
    if len(seg) == 0:
        return None
    best_off = int(np.argmax(seg)) + start
    best_score = float(seg.max())

    hole_x = best_off
    out.update({
        "piece_x": piece_x, "hole_x": hole_x,
        "hole_pct": round(100 * hole_x / w, 1),
        "match_score": round(best_score, 3),
        "offset": max(0, hole_x - piece_x),
    })
    return out


if __name__ == "__main__":
    import sys, glob
    files = sys.argv[1:] or sorted(glob.glob("shots/so_85729884045_puz?.png"))
    for f in files:
        print(f, "->", detect(f))
