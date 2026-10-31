#!/usr/bin/env python3
"""local_solver.py — A2: gap detection presisi via OpenCV + ALPHA MASK.

Kunci: piece = 44x44 RGBA, alpha = SHAPE mask (bukan kotak penuh).
→ gap di puzzle = lokasi di mana konten puzzle COCOK dengan piece ber-mask.

Metode utama: masked template matching (alpha mask) di banyak skala,
+ fallback edge/dev untuk ranking kandidat.
"""
import base64
import numpy as np
import cv2


def _decode(b64, color=True):
    if not b64:
        return None
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    raw = base64.b64decode(b64)
    arr = np.frombuffer(raw, np.uint8)
    flag = cv2.IMREAD_UNCHANGED if color else cv2.IMREAD_COLOR
    return cv2.imdecode(arr, flag)


def _puzzle_bgr(puzzle):
    if puzzle is None:
        return None
    if puzzle.ndim == 3 and puzzle.shape[2] == 4:
        return cv2.cvtColor(puzzle, cv2.COLOR_BGRA2BGR)
    return puzzle


def candidates(puzzle_b64, piece_b64, topk=4):
    """Return (list_gap_x prioritas, debug)."""
    puzzle = _puzzle_bgr(_decode(puzzle_b64, color=False))
    piece = _decode(piece_b64, color=True)   # RGBA penting
    if puzzle is None or piece is None:
        return [], {"err": "decode"}
    ph, pw = puzzle.shape[:2]
    kh, kw = piece.shape[:2]
    dbg = {"puzzle": [pw, ph], "piece": [kw, kh]}
    scored = {}

    def add(x, score, src):
        x = int(round(x))
        if 4 <= x <= pw - 4 and (x not in scored or score > scored[x][0]):
            scored[x] = (float(score), src)

    # ---- METODE UTAMA: masked template matching pakai alpha piece ----
    if piece.ndim == 3 and piece.shape[2] == 4:
        bgr = piece[:, :, :3]
        alpha = piece[:, :, 3]
        mask = (alpha > 30).astype(np.uint8) * 255
        # perluas mask sedikit biar inkludif tepi
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), 1)
        if cv2.countNonZero(mask) < 100:
            mask = None
        try:
            res = cv2.matchTemplate(puzzle, bgr, cv2.TM_CCORR_NORMED, mask=mask)
            res = np.nan_to_num(res, nan=0.0, posinf=0.0, neginf=0.0)
            _, mv, _, ml = cv2.minMaxLoc(res)
            # mask the top-K peaks (kosongkan sekitar puncak lalu cari lagi)
            flat = res.copy()
            for i in range(min(3, topk)):
                _, mvx, _, mlx = cv2.minMaxLoc(flat)
                add(mlx[0], mvx, "mask" if i == 0 else f"mask{i}")
                x0 = max(0, mlx[0] - kw // 2); x1 = min(flat.shape[1], mlx[0] + kw // 2)
                flat[:, x0:x1] = 0
            dbg["mask_tmpl"] = {"x": int(ml[0]), "s": round(float(mv), 4)}
        except Exception as e:
            dbg["mask_err"] = str(e)[:60]

    g = cv2.cvtColor(puzzle, cv2.COLOR_BGR2GRAY)
    gp = cv2.cvtColor(piece[:, :, :3], cv2.COLOR_BGR2GRAY)

    # ---- fallback: edge template ----
    ex_p = cv2.convertScaleAbs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3))
    ex_k = cv2.convertScaleAbs(cv2.Sobel(gp, cv2.CV_32F, 1, 0, ksize=3))
    res_e = cv2.matchTemplate(ex_p, ex_k, cv2.TM_CCOEFF_NORMED)
    _, mve, _, mle = cv2.minMaxLoc(res_e)
    add(mle[0], mve * 0.6, "edge")
    dbg["edge"] = {"x": int(mle[0]), "s": round(float(mve), 4)}

    # ---- fallback: dev/gap-blob ----
    win = max(6, kw // 3)
    bl = cv2.GaussianBlur(g, (0, 0), 6)
    dev = cv2.absdiff(g, bl).astype(np.float32)
    col = dev.sum(axis=0); col_n = col / (col.max() + 1e-9)
    pk = [(x, float(col_n[x])) for x in range(win, pw - win)
          if col_n[x] == col_n[x - win:x + win + 1].max() and col_n[x] > 0.5]
    pk.sort(key=lambda t: -t[1])
    for x, s in pk[:2]:
        add(x, s * 0.5, "dev")

    ranked = sorted(scored.items(), key=lambda kv: -kv[1][0])[:topk]
    out = [x for x, _ in ranked]
    dbg["candidates"] = [{"x": x, "s": round(scored[x][0], 3), "src": scored[x][1]} for x in out]
    return out, dbg


def find_gap_x(puzzle_b64, piece_b64):
    xs, dbg = candidates(puzzle_b64, piece_b64, topk=1)
    return (xs[0] if xs else None), dbg


def solve_local(puzzle_b64, piece_b64, puzzle_disp_w, canvas_w=None):
    xs, dbg = candidates(puzzle_b64, piece_b64, topk=1)
    if not xs:
        return None, dbg
    bw = canvas_w or dbg["puzzle"][0]
    scale = puzzle_disp_w / bw if bw else 1.0
    tgt = int(round(xs[0] * scale))
    dbg["target_slider"] = tgt
    return tgt, dbg


if __name__ == "__main__":
    import sys, json
    pz, pc, w = sys.argv[1], sys.argv[2], float(sys.argv[3])
    t, d = solve_local(pz, pc, w)
    print("target:", t); print("debug:", json.dumps(d))
