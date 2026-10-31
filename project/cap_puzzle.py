#!/usr/bin/env python3
"""cap_puzzle.py — buka captcha, dump puzzle.png + piece.png (bitmap asli), biar bisa uji local_solver offline.
"""
import sys, time, base64, json
from playwright.sync_api import sync_playwright

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6285849159568"
PROXY = open("/root/shopee-farm/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://" + HOST, "username": USER, "password": PASS},
                      ignore_https_errors=True, viewport={"width": 1280, "height": 900})
    c.add_cookies([{"name": "shopee_webLanguage", "value": "id", "domain": ".shopee.co.id", "path": "/"}])
    p = c.new_page()
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    p.wait_for_selector("input[name='phone']", timeout=45000); time.sleep(4)
    try:
        mb = p.locator("button.shopee-button-outline").first
        if mb.count() and mb.is_visible(): mb.click(timeout=2500, force=True); time.sleep(3)
    except Exception: pass
    inp = p.locator("input[name='phone']").first
    inp.click(timeout=5000); inp.type(PHONE, delay=45); time.sleep(4)
    for lbl in ("BERIKUTNYA", "Berikutnya"):
        try: p.locator(f"button:has-text('{lbl}')").first.click(timeout=3000, force=True); break
        except Exception: pass
    time.sleep(3)
    for i in range(8):
        ok = p.evaluate("""()=>{const t=[...document.querySelectorAll('button,a,div')].reverse().find(e=>{const x=(e.innerText||'').trim();return x==='Setuju'||x==='SETUJU';});if(t){t.click();return true;}return false;}""")
        if ok: time.sleep(3); break
        time.sleep(2)
    for i in range(45):
        time.sleep(1.5)
        cs = p.evaluate("()=>[...document.querySelectorAll('canvas')].map(c=>({w:c.width,h:c.height,d:c.getAttribute('draggable')}))")
        if cs: break
    for w in range(12):
        if "Memuat" not in p.evaluate("()=>document.body.innerText||''"): break
        time.sleep(1.5)
    # dump puzzle + piece bitmap + rects
    info = p.evaluate("""()=>{
      const pz=document.querySelector("aside canvas[draggable=false], #NEW_CAPTCHA canvas[draggable=false]");
      const pc=document.querySelector("aside canvas[draggable=true], #NEW_CAPTCHA canvas[draggable=true]");
      const out={};
      if(pz){const r=pz.getBoundingClientRect();out.puzzle=pz.toDataURL('image/png').split(',')[1];
             out.puzzle_rect={x:r.x,y:r.y,w:r.width,h:r.height};out.puzzle_canvas={w:pz.width,h:pz.height};}
      if(pc){const r=pc.getBoundingClientRect();out.piece=pc.toDataURL('image/png').split(',')[1];
             out.piece_rect={x:r.x,y:r.y,w:r.width,h:r.height};}
      return out;}""")
    open("/root/shopee-farm/capture/puzzle.json","w").write(json.dumps(info))
    print("[cap] puzzle rect:", info.get("puzzle_rect"), "canvas:", info.get("puzzle_canvas"))
    print("[cap] piece rect:", info.get("piece_rect"))
    print("[cap] saved capture/puzzle.json")
    time.sleep(3); c.close(); b.close()
