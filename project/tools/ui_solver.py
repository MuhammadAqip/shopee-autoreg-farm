"""Solver captcha Shopee — UI-driven (Playwright).

Pendekatan (sesuai hasil RE opsi C/E):
  Fungsi kripto SDK captcha TERKUNCI di IIFE internal — tidak bisa dipanggil
  dari luar, tidak ada global hook. Solusinya: JANGAN panggil kripto.
  Biarkan SDK captcha bekerja sendiri, dan jawab challenge lewat INTERAKSI
  UI seperti manusia (event mouse bertahap).

Komponen:
  - human_move(page, x, y)          → gerak mouse bertahap + jitter
  - human_click(page, x, y)         → mousedown/mousemove/mouseup dgn delay
  - human_drag(page, x1,y1, x2,y2)  → geser slider bertahap (easing)
  - find_captcha_elements(page)     → deteksi slider track / puzzle / canvas
  - solve_slider(page, offset)      → geser sesuai offset
  - solve_click(page, points)       → klik titik objek

Jawaban (dari bundle, struktur verify):
  klik  → captcha_top_left_x/y, captcha_box_width/height
  geser → slider_end_pos, slider_start_x/y, box_w/h
  + captcha_start_timestamp/end_timestamp (timing), captcha_move_type
"""
import random
import time
from pathlib import Path

SHOT_DIR = Path("/root/shopee-farm/shots")
SHOT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------- gerak manusia ----------------

def _ease(t: float) -> float:
    """Ease-in-out cubic — kurva gerak manusia lebih natural dari linear."""
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def human_move(page, x0, y0, x1, y1, steps=None, jitter=1.5):
    """Gerak mouse dari (x0,y0) ke (x1,y1) bertahap dgn easing + jitter."""
    dist = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if steps is None:
        steps = max(8, int(dist / 6))
    page.mouse.move(x0, y0)
    for i in range(1, steps + 1):
        t = _ease(i / steps)
        x = x0 + (x1 - x0) * t + random.uniform(-jitter, jitter)
        y = y0 + (y1 - y0) * t + random.uniform(-jitter, jitter)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.004, 0.012))


def human_click(page, x, y, pre_move=True, hold_ms=None):
    """Klik seperti manusia: gerak dulu, tahan sesaat, lepas."""
    if pre_move:
        cx = x + random.uniform(-40, 40)
        cy = y + random.uniform(-30, 30)
        human_move(page, cx, cy, x, y, jitter=1.0)
    page.mouse.down()
    time.sleep((hold_ms or random.randint(45, 120)) / 1000)
    page.mouse.up()


def human_drag(page, x0, y0, x1, y1, steps=None):
    """Geser slider: gerak ke grip → tahan → geser bertahap → lepas."""
    human_move(page, x0 - 30, y0 + random.uniform(-8, 8), x0, y0, jitter=1.0)
    page.mouse.down()
    time.sleep(random.uniform(0.08, 0.2))
    dist = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if steps is None:
        steps = max(15, int(dist / 4))
    for i in range(1, steps + 1):
        t = _ease(i / steps)
        x = x0 + (x1 - x0) * t + random.uniform(-0.8, 0.8)
        y = y0 + (y1 - y0) * t + random.uniform(-1.2, 1.2)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.008, 0.02))
    # mikro-pause sebelum lepas (manusia sering melakukannya)
    time.sleep(random.uniform(0.05, 0.15))
    page.mouse.up()


# ---------------- deteksi DOM captcha ----------------

FIND_JS = r"""
(() => {
  const q = (s) => Array.from(document.querySelectorAll(s));
  const rect = (el) => { const r = el.getBoundingClientRect();
                         return {x:r.x, y:r.y, w:r.width, h:r.height}; };
  const out = {container: !!document.querySelector('#anti_fraud_captcha'),
               canvases: [], sliders: [], grips: [], images: [], text: []};
  q('#anti_fraud_captcha canvas, .captcha canvas, canvas').forEach(c => {
    const r = rect(c); if (r.w > 30 && r.h > 20) out.canvases.push({...r, id:c.id, cls:c.className});
  });
  q('[class*=slider],[class*=track],[class*=bar]').forEach(e => {
    const r = rect(e); if (r.w > 60 && r.h < 120) out.sliders.push({...r, cls:e.className});
  });
  q('[class*=grip],[class*=btn],[class*=handle],[class*=drag]').forEach(e => {
    const r = rect(e); if (r.w > 10 && r.h > 10 && r.w < 120) out.grips.push({...r, cls:e.className});
  });
  q('#anti_fraud_captcha img, .captcha img').forEach(i => {
    const r = rect(i); if (r.w > 40) out.images.push({...r, src:(i.src||'').slice(0,80)});
  });
  q('#anti_fraud_captcha *').forEach(e => {
    const tx = (e.textContent||'').trim();
    if (tx && tx.length < 60 && e.children.length === 0) out.text.push(tx);
  });
  out.text = [...new Set(out.text)].slice(0, 15);
  return out;
})()
"""


def find_captcha_elements(page):
    try:
        return page.evaluate(FIND_JS)
    except Exception as e:
        return {"error": str(e)}


# ---------------- solve ----------------

def solve_slider(page, end_offset=None, grip_hint=None, shot=None):
    """Geser slider. end_offset = jarak geser (px dari posisi awal grip).

    Kalau end_offset None → coba hitung dari lebar track (fallback: 70%).
    Return dict hasil + posisi.
    """
    els = find_captcha_elements(page)
    grip = grip_hint
    if not grip:
        if els.get("grips"):
            grip = max(els["grips"], key=lambda g: g["w"] * g["h"])
        elif els.get("sliders"):
            s = els["sliders"][0]
            grip = {"x": s["x"], "y": s["y"] + s["h"] / 2, "w": 40, "h": s["h"]}
    if not grip:
        return {"ok": False, "err": "no grip/slider found", "els": els}

    x0 = grip["x"] + grip["w"] / 2
    y0 = grip["y"] + grip["h"] / 2
    track_w = 260
    if els.get("sliders"):
        track_w = max(s["w"] for s in els["sliders"])
    if end_offset is None:
        end_offset = track_w * 0.7
    x1 = x0 + end_offset

    if shot:
        page.screenshot(path=str(SHOT_DIR / f"{shot}_before.png"))
    human_drag(page, x0, y0, x1, y0)
    time.sleep(1.2)
    if shot:
        page.screenshot(path=str(SHOT_DIR / f"{shot}_after.png"))
    return {"ok": True, "from": [x0, y0], "to": [x1, y0], "offset": end_offset}


def solve_click(page, points, shot=None):
    """Klik beberapa titik (koordinat absolut) secara berurutan seperti manusia."""
    done = []
    for (x, y) in points:
        human_click(page, x, y)
        done.append([x, y])
        time.sleep(random.uniform(0.15, 0.4))
    if shot:
        page.screenshot(path=str(SHOT_DIR / f"{shot}_clicked.png"))
    return {"ok": True, "clicked": done}


def click_center(page, el, shot=None):
    """Klik tengah elemen (mis. tombol 'Klik untuk memverifikasi Anda')."""
    if not el:
        return {"ok": False, "err": "no element"}
    x = el["x"] + el["w"] / 2
    y = el["y"] + el["h"] / 2
    human_click(page, x, y)
    if shot:
        page.screenshot(path=str(SHOT_DIR / f"{shot}_center.png"))
    return {"ok": True, "center": [x, y]}


# ---------------- orkestrasi ----------------

def attempt_solve(page, coords=None, kind="auto", shot_prefix="capsolve"):
    """Coba jawab captcha.

    kind: "slider" | "click" | "auto"
    coords: untuk click → list of (x,y); untuk slider → end_offset (angka)
    Return dict status.
    """
    els = find_captcha_elements(page)
    res = {"container": els.get("container"), "canvases": len(els.get("canvases", [])),
           "sliders": len(els.get("sliders", [])), "grips": len(els.get("grips", [])),
           "text": els.get("text", [])[:6]}

    if kind in ("auto", "click") and els.get("grips"):
        g = max(els["grips"], key=lambda x: x["w"] * x["h"])
        # kalau grip kecil & ada canvas → kemungkinan tombol "klik untuk verifikasi"
        if g["w"] < 60:
            r = click_center(page, g, shot=f"{shot_prefix}_entry")
            res["action"] = "entry_click"
            res["result"] = r
            return res

    if kind in ("auto", "slider") and els.get("grips"):
        off = coords if isinstance(coords, (int, float)) else None
        r = solve_slider(page, end_offset=off, shot=shot_prefix)
        res["action"] = "slider_drag"
        res["result"] = r
        return res

    if kind == "click" and coords:
        r = solve_click(page, coords, shot=shot_prefix)
        res["action"] = "multi_click"
        res["result"] = r
        return res

    res["action"] = "none"
    res["hint"] = "tidak ada grip/slider terdeteksi — cek screenshot manual"
    return res
