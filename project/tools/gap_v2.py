"""Gap detection v2 — edge-seam + template-match.

Ground truth: crop puzzle 280x150, piece di kiri (~3%), celah di suatu tempat.

Metode:
  A) EDGE-SEAM: celah = boundary puzzle -> muncul garis seam (gradien tinggi
     vertikal). Cari kolom dgn "edge energy" tinggi TERISOLASI di tengah.
  B) TEMPLATE-MATCH: piece (region kiri) di-match ke gambar -> posisi celah =
     posisi match terbaik di luar region piece.
"""
import sys
import numpy as np
from PIL import Image

def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.float32)

def edge_seam(a):
    """Cari kolom celah via gradien vertikal (discontinuity/gap boundary)."""
    h, w, _ = a.shape
    gray = a.mean(2)
    # gradien horizontal absolut per kolom
    gx = np.abs(np.diff(gray, axis=1))          # h x (w-1)
    col_energy = gx.mean(axis=0)                # w-1
    # celah terjauh: cari peak di tengah (dan bukan tepi)
    lo, hi = int(w*0.10), int(w*0.60)
    seg = col_energy[lo:hi]
    if not len(seg): return None
    # peak = seam
    peak = int(np.argmax(seg)) + lo
    return {"edge_gap_x": peak, "edge_pct": round(100*peak/w,1)}

def template_match(a):
    """Match piece (region kiri 0-12%) ke gambar -> cari posisi cocok."""
    h, w, _ = a.shape
    pw = int(w*0.14)                    # lebar piece
    piece = a[:, int(w*0.02):int(w*0.02)+pw, :]
    if piece.size == 0: return None
    # sliding window: cari kolom start dgn MSE terendah vs piece
    best_x, best_v = None, 1e30
    for x in range(int(w*0.02)+pw, w-pw):
        win = a[:, x:x+pw, :]
        if win.shape != piece.shape: continue
        v = np.mean((win-piece)**2)
        if v < best_v:
            best_v, best_x = v, x
    return {"tm_gap_x": best_x, "tm_pct": round(100*best_x/w,1), "mse": round(float(best_v),1)}

def analyze(path, debug=False):
    a = load(path)
    h, w, _ = a.shape
    out = {"W": w, "H": h}
    es = edge_seam(a); tm = template_match(a)
    if es: out.update(es)
    if tm: out.update(tm)
    # gabung: pakai template-match sebagai utama, edge sebagai verifikasi
    out["gap_x"] = tm["tm_gap_x"] if tm else (es["edge_gap_x"] if es else int(w*0.2))
    out["piece_x"] = int(w*0.03)
    out["offset"] = max(0, out["gap_x"] - out["piece_x"])
    out["gap_pct"] = round(100*out["gap_x"]/w, 1)
    return out

if __name__ == "__main__":
    for f in sys.argv[1:] or ["shots/cur_puzzle_3x.png"]:
        print(f, "->", analyze(f))
