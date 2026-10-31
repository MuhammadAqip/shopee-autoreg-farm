"""Gap detection v3 — cari celah (slot DASHED) di SELURUH lebar.

Ground truth (multi_1): piece ~10-12%, celah ~78-82%. Celah = area kosong
dengan garis putus-putus (dashed) / area tanpa tekstur gambar.

Metode:
  1. PIECE: region paling kiri yg menonjol (tepi kiri gambar).
  2. GAP: cari kolom dgn karakteristik "lubang" (rendah tekstur / dashed)
     di seluruh lebar (lebar piece ke kanan), pilih yg paling mungkin.
"""
import numpy as np
from PIL import Image


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.float32)


def detect(path, piece_frac=0.11):
    a = load(path)
    h, w, _ = a.shape
    gray = a.mean(2)

    # --- tekstur lokal per kolom (variansi dalam window vertikal) ---
    tex = np.array([gray[:, x].std() for x in range(w)])

    # piece kiri: ujung kiri
    piece_x = int(w * piece_frac)

    # --- GAP: cari kolom celah di KANAN piece ---
    # celah = area dgn tekstur rendah ATAU seam tajam (dashed boundary).
    # Scan dari piece ke kanan, cari window dgn kombinasi:
    #   (a) tekstur rendah (area kosong/polos)  ATAU
    #   (b) gradien tinggi (garis dashed)
    gx = np.abs(np.diff(gray, axis=1)).mean(axis=0)   # w-1, edge energy

    # gabung: celah kandidat = peak edge energy di kanan piece
    lo = int(w * (piece_frac + 0.15))
    hi = int(w * 0.92)
    if hi <= lo:
        lo, hi = int(w*0.3), int(w*0.9)
    seg_e = gx[lo:hi]
    peak_edge = int(np.argmax(seg_e)) + lo if len(seg_e) else int(w*0.75)

    # alternatif: area tekstur paling rendah di kanan
    seg_t = tex[lo:hi]
    low_tex = int(np.argmin(seg_t)) + lo if len(seg_t) else int(w*0.75)

    gap_x = peak_edge
    offset = max(0, gap_x - piece_x)
    return {"W": w, "H": h, "piece_x": piece_x, "piece_pct": round(100*piece_x/w,1),
            "gap_x": gap_x, "gap_pct": round(100*gap_x/w,1),
            "alt_lowtex_x": low_tex, "alt_lowtex_pct": round(100*low_tex/w,1),
            "offset": offset, "offset_pct": round(100*offset/w,1),
            "offset_screen": offset}


if __name__ == "__main__":
    import sys
    for f in sys.argv[1:] or ["shots/cur_puzzle.png"]:
        print(f, "->", detect(f))
