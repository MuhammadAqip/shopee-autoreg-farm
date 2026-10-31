#!/usr/bin/env python3
"""solve_captcha.py — modul solve 3 tipe captcha Shopee (SadCaptcha).

Diimpor oleh shopee_hybrid.py. Auto-detect tipe via selector (bukan teks).
"""
import time, random, re, requests

API = "https://www.sadcaptcha.com/api/v1"

IC_PUZZLE = "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false]"
IC_PIECE  = "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"
IC_BUTTON = "div:has(> svg + svg)"
PZ_BUTTON = 'aside[aria-modal=true] div[style*="translateX(0px)"]'
PZ_PUZZLE = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=false]"
PZ_PIECE  = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=true]"
ID_PUZZLE = "#NEW_CAPTCHA canvas, aside canvas"
ID_PIECE  = "#NEW_CAPTCHA img, aside img"
ID_VERIFY = ".rb6XLo, #NEW_CAPTCHA button:not(:has(*)), aside button:not(:has(*))"


def _dataurl(p, sel):
    return p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;
      if(e.tagName==='CANVAS')return e.toDataURL('image/png').split(',')[1];
      if(e.tagName==='IMG'){const u=e.src||'';return u.includes(',')?u.split(',')[1]:null;}return null;}""", sel)


def _rect(p, sel):
    return p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();
      return {x:r.x,y:r.y,w:r.width,h:r.height};}""", sel)


def _present(p, sels):
    return p.evaluate("(sels)=>{for(const s of sels){try{if(document.querySelector(s))return s;}catch(e){}}return null;}", sels)


def _api(path, body, key):
    try:
        r = requests.post(f"{API}{path}?licenseKey={key}", json=body, timeout=45)
        if r.status_code != 200:
            return None, f"{r.status_code}:{r.text[:120]}"
        return r.json(), None
    except Exception as e:
        return None, str(e)[:120]


def _bezier(start, end, steps):
    c1 = {"x": start[0]+(end[0]-start[0])*(0.2+random.random()*0.2), "y": start[1]+(random.random()*15-5)}
    c2 = {"x": start[0]+(end[0]-start[0])*(0.6+random.random()*0.2), "y": end[1]+(random.random()*10-5)}
    out = []
    for i in range(steps+1):
        t = i/steps
        x = (1-t)**3*start[0]+3*(1-t)**2*t*c1["x"]+3*(1-t)*t**2*c2["x"]+t**3*end[0]
        y = (1-t)**3*start[1]+3*(1-t)**2*t*c1["y"]+3*(1-t)*t**2*c2["y"]+t**3*end[1]
        out.append((x, y))
    return out


def _approach(p, x, y):
    sx = x-80-random.random()*40; sy = y+40+random.random()*30
    for (px, py) in _bezier((sx, sy), (x, y), 8+int(random.random()*4)):
        p.mouse.move(px, py); time.sleep(0.015+random.random()*0.025)


def solve(p, key):
    """Auto-detect tipe & solve. Return dict hasil."""
    if _present(p, [IC_PIECE]):
        return solve_image_crawl(p, key)
    if _present(p, [PZ_PIECE]):
        return {"err": "puzzle-not-impl"}
    if _present(p, [ID_PUZZLE, ID_VERIFY]):
        return {"err": "image-drag-not-impl"}
    return {"err": "no-captcha-detected"}


def solve_image_crawl(p, key):
    btn = _rect(p, IC_BUTTON)
    if not btn:
        btn = p.evaluate("""()=>{let f=null;document.querySelectorAll('div,button,span').forEach(e=>{
          const r=e.getBoundingClientRect();if(r.width>=28&&r.width<=56&&r.height>=28&&r.height<=56&&r.top>480){
          if(!f||r.top<f.y)f={x:r.x,y:r.y,w:r.width,h:r.height};}});return f;}""")
    if not btn: return {"err": "no btn"}
    pz = _dataurl(p, IC_PUZZLE); pc = _dataurl(p, IC_PIECE)
    if not pz or not pc: return {"err": "no img"}

    # ==== CACHE LOOKUP: puzzle sama → pakai solusi lama, SKIP SadCaptcha ====
    try:
        from captcha_cache import CaptchaCache
        cc = CaptchaCache()
    except Exception:
        cc = None
    target = None
    if cc:
        cached = cc.lookup(pz, pc)
        if cached is not None:
            target = cached

    if target is None:
        pre, err = _api("/shopee-image-crawl-pre-analyze", {"image_b64": pz}, key)
        if err and "401" in str(err): return {"err": "CREDITS_EMPTY"}

    sx, sy = btn["x"]+btn["w"]/2, btn["y"]+btn["h"]/2
    pz_rect = _rect(p, IC_PUZZLE)
    _approach(p, sx, sy)
    p.mouse.move(sx, sy); p.mouse.down(); time.sleep(0.15)
    traj = []; bar_w = pz_rect["w"]; limit = bar_w*0.85
    for px in range(0, int(limit), 3):
        p.mouse.move(sx+px, sy-px); time.sleep(0.02)
        pr = p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;
          const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,style:e.getAttribute('style')||''};}""", IC_PIECE)
        if not pr: continue
        pcx = pr["x"]+pr["w"]/2; pcy = pr["y"]+pr["h"]/2
        pxp = round((pcx-pz_rect["x"])/pz_rect["w"], 4); pyp = round((pcy-pz_rect["y"])/pz_rect["h"], 4)
        a = 0.0
        mm = re.search(r"rotate\(([-0-9.]+)deg", pr["style"])
        if mm: a = float(mm.group(1))
        traj.append({"pixels_from_slider_origin": px, "piece_rotation_angle": a,
                     "piece_center": {"proportionX": pxp, "proportionY": pyp}})
    traj.sort(key=lambda x: x["pixels_from_slider_origin"])

    if target is None:
        if len(traj) < 12:
            p.mouse.up(); return {"err": "traj short", "n": len(traj)}
        sol, err = _api("/shopee-image-crawl",
                        {"puzzle_image_b64": pz, "piece_image_b64": pc, "slide_piece_trajectory": traj}, key)
        if not sol:
            p.mouse.up(); return {"err": err}
        target = sol.get("pixelsFromSliderOrigin")
        if cc and target is not None:
            cc.record(pz, pc, int(target))

    # drag ke target (dari cache ATAU fresh solve)
    p.mouse.move(sx, sy); time.sleep(0.1)
    for i in range(0, int(target), 8):
        p.mouse.move(sx+i, sy); time.sleep(0.008)
    ov = random.choice([1, 2, 3])
    p.mouse.move(sx+target+ov, sy+ov); p.mouse.move(sx+target, sy)
    time.sleep(0.2); p.mouse.up()
    src = "cache" if (cc and cc.lookup(pz, pc) is not None and target is not None) else "api"
    return {"type": "image_crawl", "target": target, "traj": len(traj), "src": src,
            "pz": pz, "pc": pc}


if __name__ == "__main__":
    print("solve_captcha module — import from shopee_hybrid.py")
