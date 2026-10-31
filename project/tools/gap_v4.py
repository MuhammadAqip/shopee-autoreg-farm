"""Gap detection v4 — Laplacian (piece) + HoughLines (dashed slot).

Berdasarkan blueprint vision:
  - PIECE = blok texture-energy tinggi (Laplacian variance) -> boundingRect.
  - SLOT  = rectangle dashed (Canny + HoughLinesP) -> slot left edge.
  - distance = slot_x - piece_x
"""
import cv2
import numpy as np


def detect(path):
    img = cv2.imread(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    out = {"W": w, "H": h}

    # --- PIECE: texture energy (piece punya konten gambar, slot kosong) ---
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    var = cv2.boxFilter(lap * lap, -1, (15, 15))
    _, pm = cv2.threshold(var, var.mean() * 1.4, 255, cv2.THRESH_BINARY)
    pm = pm.astype(np.uint8)
    cs, _ = cv2.findContours(pm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    piece_x = None
    if cs:
        big = max(cs, key=cv2.contourArea)
        bx, by, bw, bh = cv2.boundingRect(big)
        if bw > w * 0.08:
            piece_x = bx
    out["piece_x"] = piece_x

    # --- SLOT: dashed rectangle -> garis vertikal via HoughLinesP ---
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=25,
                            minLineLength=15, maxLineGap=6)
    verts = []
    if lines is not None:
        for l in lines:
            x1, y1, x2, y2 = np.asarray(l).ravel()[:4]
            if abs(x1 - x2) < 6 and abs(y2 - y1) > h * 0.15:   # vertikal
                verts.append((x1 + x2) // 2)
    slot_x = None
    if verts:
        # celah di KANAN piece; ambil median vertikal di kanan
        right = [v for v in verts if v > (piece_x or 0) + w * 0.1]
        slot_x = int(np.median(right)) if right else int(np.median(verts))
    out["slot_x"] = slot_x
    out["n_verts"] = len(verts)

    # --- gabung ---
    if piece_x is None:
        piece_x = int(w * 0.11)
    if slot_x is None:
        slot_x = int(w * 0.78)
    out["piece_pct"] = round(100 * piece_x / w, 1)
    out["slot_pct"] = round(100 * slot_x / w, 1)
    out["offset"] = max(0, slot_x - piece_x)
    out["offset_pct"] = round(100 * out["offset"] / w, 1)
    return out


if __name__ == "__main__":
    import sys
    for f in sys.argv[1:] or ["shots/so_puzzle_3x.png"]:
        print(f, "->", detect(f))
