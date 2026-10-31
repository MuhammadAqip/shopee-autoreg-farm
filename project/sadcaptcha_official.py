#!/usr/bin/env python3
"""sadcaptcha_official.py — implementasi alur RESMI SadCaptcha utk Shopee IMAGE_CRAWL.

Replika persis chrome-ext resmi (gbiz123/shopee-captcha-solver-chrome-extension):
  1. detect IMAGE_CRAWL (#NEW_CAPTCHA / #captchaMask)
  2. POST /shopee-image-crawl-pre-analyze {image_b64} -> {slideXProportion, skipRecommended}
  3. sweep trajectory (diagonal) -> slide_piece_trajectory (>=12 baris)
  4. POST /shopee-image-crawl {puzzle_image_b64, piece_image_b64, slide_piece_trajectory}
     -> pixelsFromSliderOrigin
  5. GESTURE SWING drag ke solution (toU/toPx, 4 pass) + release nudge
"""
import math, random, time, base64
import requests

API = "https://www.sadcaptcha.com/api/v1"

# selector resmi
S_PUZZLE = "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false], div:not(#puzzleContainer) > img"
S_PIECE  = "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"
# grip: versi baru tak punya #sliderContainer → cari via JS (kotak ~40px di bawah puzzle)
S_BUTTON = "#sliderContainer > div > div"   # versi lama (fallback)
S_RESET  = "#NEW_CAPTCHA svg[viewBox='0 0 16 16'], aside svg[viewBox='0 0 16 16']"
S_PRESENCE = ["#NEW_CAPTCHA", "#captchaMask"]

_JS_FIND_GRIP = """()=>{
  const pz=document.querySelector("#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false], div:not(#puzzleContainer)>img");
  if(!pz) return null;
  const pb=pz.getBoundingClientRect().bottom;
  let best=null, bx=1e9;
  document.querySelectorAll('#NEW_CAPTCHA *, aside *').forEach(e=>{
    const r=e.getBoundingClientRect();
    if(r.width>=34&&r.width<=60&&r.height>=34&&r.height<=60&&r.top>pb){
      if(r.x<bx){bx=r.x;best=e;}}});
  if(!best) return null;
  const r=best.getBoundingClientRect();
  return {x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height,top:r.top,left:r.left};
}"""

# konstanta resmi
SCATTER_BLOCK_PX = 30
SCATTER_SWEEP = True
GESTURE_AMP_U = 1.5
GESTURE_PASSES = 4
GESTURE_PACE_MS = 2
SWING_SAFE_PX = 12
PAUSE_BEFORE_NUDGE_MS = (900, 2100)
PAUSE_BEFORE_RELEASE_MS = (750, 1450)
SKIP_CAP = 3
PRESS_SETTLE_MS = 150
SAMPLE_SETTLE_MS = 20
OVERSHOOT_PX = 15
MIN_TRAJECTORY_ROWS = 12
MOUSE_STEP = 3


def _api_post(url, payload, key):
    r = requests.post(f"{url}?licenseKey={key}", json=payload, timeout=30)
    if r.status_code == 400:
        raise ValueError(f"400 bad request: {r.text[:120]}")
    if r.status_code == 401:
        raise ValueError("401 bad license/out of credits")
    return r.json()


def credits(key):
    return requests.get(f"{API}/license/credits?licenseKey={key}", timeout=20).json()


def pre_analyze(puzzle_b64, key):
    return _api_post(f"{API}/shopee-image-crawl-pre-analyze", {"image_b64": puzzle_b64}, key)


def image_crawl(puzzle_b64, piece_b64, trajectory, key):
    return _api_post(f"{API}/shopee-image-crawl", {
        "puzzle_image_b64": puzzle_b64,
        "piece_image_b64": piece_b64,
        "slide_piece_trajectory": trajectory,
    }, key)["pixelsFromSliderOrigin"]


def element_center(p, sel):
    r = p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;
      const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height,top:r.top,left:r.left};}""", sel)
    return r


def button_center(p):
    """Cari grip: coba selector lama dulu, fallback ke JS (kotak 40px di bawah puzzle)."""
    c = element_center(p, S_BUTTON)
    if c and c.get("w"):
        return c
    return p.evaluate(_JS_FIND_GRIP)


def element_b64(p, sel):
    return p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;
      if(e.tagName==='CANVAS'){return e.toDataURL('image/png').split(',')[1];}
      const src=e.getAttribute('src')||e.src||'';return src.split(',')[1]||null;}""", sel)


def piece_style_rotate(p, sel):
    return p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return {angle:0,propX:0,propY:0};
      const st=e.getAttribute('style')||'';let a=0;const m=st.match(/rotate\\(([-0-9.]+)deg\\)/);if(m)a=parseFloat(m[1]);
      return {angle:a};}""", sel)


def solve_image_crawl(p, key, refresh_fn=None):
    """Return pixelsFromSliderOrigin (drag distance) atau None."""
    for attempt in range(1, SKIP_CAP + 1):
        # 2. pre-analyze
        puzzle = element_b64(p, S_PUZZLE)
        if not puzzle:
            return None
        try:
            info = pre_analyze(puzzle, key)
        except Exception as e:
            print("[sad] pre-analyze err:", str(e)[:80]); return None
        print("[sad] pre-analyze:", {k: info.get(k) for k in ("slideXProportion", "skipRecommended")})
        tp = info.get("slideXProportion")
        if (info.get("skipRecommended") or (isinstance(tp, (int, float)) and tp >= 0.99)) and attempt < SKIP_CAP:
            if refresh_fn:
                refresh_fn()
            continue

        piece = element_b64(p, S_PIECE)
        btn = button_center(p)
        pz = element_center(p, S_PUZZLE)
        if not (piece and btn and pz):
            return None
        sx, sy = btn["x"], btn["y"]
        # 5. sweep trajectory
        traj = _sweep(p, sx, sy, pz, info.get("slideXProportion"))
        if len(traj) < MIN_TRAJECTORY_ROWS:
            print("[sad] traj < min:", len(traj)); p.mouse.up(); return None
        try:
            sol = image_crawl(puzzle, piece, traj, key)
        except Exception as e:
            print("[sad] image-crawl err:", str(e)[:80]); p.mouse.up(); return None
        print("[sad] solution px =", sol)
        _swing_drag(p, sx, sy, sol, pz["w"])
        return sol
    return None


def _sweep(p, sx, sy, pz, maxProp):
    """Sweep diagonal, rekam trajectory. Mouse sudah DOWN."""
    limit = pz["w"] * 0.85
    maxProp = maxProp if isinstance(maxProp, (int, float)) else None
    blocks = []
    base = 0
    while base < limit:
        block = [round(x) for x in range(base, min(base + SCATTER_BLOCK_PX, limit), MOUSE_STEP)]
        if SCATTER_SWEEP:
            random.shuffle(block)
        blocks.append(block)
        base += SCATTER_BLOCK_PX
    traj = []
    times_not_moved = 0
    stopPx = None
    stopped = False
    p.mouse.move(sx, sy); p.mouse.down(); time.sleep(PRESS_SETTLE_MS / 1000)
    for block in blocks:
        for pixel in block:
            p.mouse.move(sx + pixel, sy - pixel)   # diagonal
            time.sleep(SAMPLE_SETTLE_MS / 1000)
            ele = _traj_ele(p, pixel, pz)
            traj.append(ele)
            if maxProp is not None and ele["piece_center"]["proportionX"] >= maxProp:
                if stopPx is None:
                    stopPx = pixel
                elif pixel - stopPx >= OVERSHOOT_PX:
                    stopped = True; break
            if len(traj) >= 100 / MOUSE_STEP:
                if _not_moving(traj):
                    times_not_moved += 1
                else:
                    times_not_moved = 0
                if times_not_moved >= 10 / MOUSE_STEP:
                    stopped = True; break
        if stopped:
            break
    traj.sort(key=lambda t: t["pixels_from_slider_origin"])
    return traj


def _traj_ele(p, pixel, pz):
    pc = element_center(p, S_PIECE)
    rot = piece_style_rotate(p, S_PIECE).get("angle", 0)
    px_ = ((pc["x"] - pz["left"]) / pz["w"]) if pz["w"] else 0
    py_ = ((pc["y"] - pz["top"]) / pz["h"]) if pz["h"] else 0
    return {"pixels_from_slider_origin": int(pixel), "piece_rotation_angle": float(rot),
            "piece_center": {"proportionX": round(px_, 4), "proportionY": round(py_, 4)}}


def _not_moving(traj):
    return len(traj) >= 2 and traj[-2]["piece_center"]["proportionX"] == traj[-1]["piece_center"]["proportionX"]


def _swing_drag(p, sx, sy, solution, puzzle_w):
    maxPx = puzzle_w * 0.85
    toU = lambda px: px / maxPx * 4 - 2
    toPx = lambda u: (u + 2) / 4 * maxPx
    aimU = toU(solution)
    releaseY = sy
    def leg(frm, to, step):
        dist = to - frm
        n = max(1, math.ceil(abs(dist) / step))
        for i in range(1, n + 1):
            p.mouse.move(sx + frm + dist * (i / n), releaseY + (random.random() * 1.6 - 0.8))
            time.sleep(GESTURE_PACE_MS / 1000)
        return to
    loU = toU(SWING_SAFE_PX)
    sides = []
    for c in range(GESTURE_PASSES):
        a = GESTURE_AMP_U * (1 - c / GESTURE_PASSES)
        room = (2 - aimU) if (c % 2 == 0) else (aimU - loU)
        a = max(0, min(a, room))
        sides.append(aimU + (a if c % 2 == 0 else -a))
    at = button_center(p)["x"] - sx
    for u in sides:
        at = leg(at, toPx(u), 13)
    at = leg(at, solution, 15)
    releasePx = toPx(round((toU(solution) + 0.02) * 1e4) / 1e4)
    time.sleep(random.randint(*PAUSE_BEFORE_NUDGE_MS) / 1000)
    p.mouse.move(sx + releasePx, sy)
    time.sleep(random.randint(*PAUSE_BEFORE_RELEASE_MS) / 1000)
    p.mouse.up()
