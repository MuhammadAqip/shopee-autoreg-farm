#!/usr/bin/env python3
"""Dump puzzle + piece b64 + ukuran tiap elemen, buat debug image_crawl vs puzzle."""
import sys, time, re, base64, json
from playwright.sync_api import sync_playwright

phone = (sys.argv[1] or "").lstrip("+0")
if phone.startswith("62"): phone = phone[2:]
px_url = sys.argv[2]

IC_PUZZLE = "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false]"
IC_PIECE  = "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"
PZ_PUZZLE = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=false]"
PZ_PIECE  = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=true]"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

pm = re.match(r"http://([^:]+):([^@]+)@([^:]+):(\d+)", px_url)
pxy = {"server": f"http://{pm.group(3)}:{pm.group(4)}", "username": pm.group(1), "password": pm.group(2)}

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--no-sandbox","--disable-blink-features=AutomationControlled"])
    c = b.new_context(user_agent=UA, locale="id-ID", proxy=pxy, viewport={"width":1280,"height":900})
    c.add_cookies([{"name":"shopee_webLanguage","value":"id","domain":".shopee.co.id","path":"/"}])
    p = c.new_page()
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
    time.sleep(3)
    for _ in range(40):
        t = p.evaluate("()=>document.body.innerText||''")
        if "Pilih bahasa" not in t and p.evaluate("()=>document.querySelectorAll('input').length")>0: break
        try: p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=1500, force=True)
        except Exception: pass
        time.sleep(1.2)
    from tools.signup_driver import fill_field
    fill_field(p, 0, phone); time.sleep(1.5)
    for sel in ["button:has-text('BERIKUTNYA')","text=BERIKUTNYA"]:
        try:
            loc = p.locator(sel).first
            if loc.count():
                bb = loc.bounding_box()
                if bb: p.mouse.move(bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2); time.sleep(0.15); p.mouse.down(); time.sleep(0.08); p.mouse.up(); break
        except Exception: continue
    # klik TOS setuju kalau muncul
    for _ in range(15):
        time.sleep(2)
        btn = p.evaluate("""()=>{let f=null;document.querySelectorAll('button,div,span,a').forEach(e=>{
          const t=(e.childElementCount===0?(e.textContent||''):'').trim();
          if(!f&&/^setuju$/i.test(t)){const r=e.getBoundingClientRect();if(r.width>0)f={x:r.x+r.width/2,y:r.y+r.height/2};}});return f;}""")
        if btn:
            p.mouse.move(btn["x"], btn["y"]); time.sleep(0.15); p.mouse.down(); time.sleep(0.08); p.mouse.up()
            print("TOS clicked", btn); continue
        _txt = p.evaluate("()=>document.body.innerText||''")
        if "Geser" in _txt or "puzzle" in _txt.lower(): break
    time.sleep(3)
    print("INSTR:", p.evaluate("()=>{const m=document.body.innerText.match(/Geser[^\\n]*/);return m?m[0]:'none';}"))
    # enumerate all canvas + img in modal
    info = p.evaluate("""()=>{
      const out=[];
      document.querySelectorAll('canvas,img').forEach(e=>{
        const r=e.getBoundingClientRect();
        if(r.width<5)return;
        out.push({tag:e.tagName, cls:(e.className||'').toString().slice(0,40),
                  draggable:e.getAttribute('draggable'), w:Math.round(r.width),h:Math.round(r.height),
                  x:Math.round(r.x),y:Math.round(r.y),
                  style:(e.getAttribute('style')||'').slice(0,60)});
      });return out;}""")
    print("ELEMENTS:")
    for e in info: print(" ", json.dumps(e))
    # ambil b64 dari kandidat puzzle & piece
    def grab(sel):
        return p.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return null;
          if(e.tagName==='CANVAS'){try{return e.toDataURL('image/png');}catch(x){return null;}}
          return e.src||null;}""", sel)
    for name, sel in [("IC_PUZZLE",IC_PUZZLE),("IC_PIECE",IC_PIECE),("PZ_PUZZLE",PZ_PUZZLE),("PZ_PIECE",PZ_PIECE)]:
        d = grab(sel)
        if d:
            raw = d.split(",")[1] if "," in d else d
            path = f"/root/shopee-farm/shots/dump_{name}_{phone}.png"
            try:
                open(path,"wb").write(base64.b64decode(raw))
                print(f"  {name}: SAVED {path} ({len(raw)} b64)")
            except Exception as ex:
                print(f"  {name}: decode fail {ex}")
        else:
            print(f"  {name}: NONE")
    p.screenshot(path=f"/root/shopee-farm/shots/dump_full_{phone}.png")
    b.close()
print("DONE")
