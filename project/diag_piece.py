#!/usr/bin/env python3
"""diag_piece.py — cek: apakah piece canvas bergerak saat drag? ukur transform sebelum/sesudah.
Juga coba dispatch event LANGSUNG ke elemen grip (bukan page-level).
"""
import sys, time, json, random, importlib.util
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
    # tunggu captcha
    for i in range(45):
        time.sleep(1.5)
        cs = p.evaluate("()=>[...document.querySelectorAll('canvas')].map(c=>({w:c.width,h:c.height,d:c.getAttribute('draggable')}))")
        if cs: break
    for w in range(12):
        if "Memuat" not in p.evaluate("()=>document.body.innerText||''"): break
        time.sleep(1.5)
    print("[diag] captcha ready", flush=True)

    # --- ukur state awal piece + grip ---
    def piece_state():
        return p.evaluate("""()=>{
          const pc=document.querySelector("aside canvas[draggable=true], #NEW_CAPTCHA canvas[draggable=true]");
          const pz=document.querySelector("aside canvas[draggable=false], #NEW_CAPTCHA canvas[draggable=false]");
          const g={};
          if(pc){const r=pc.getBoundingClientRect();g.piece={x:Math.round(r.x),y:Math.round(r.y)};g.pieceStyle=pc.parentElement?pc.parentElement.getAttribute('style'):'';}
          if(pz){const r=pz.getBoundingClientRect();g.puzzle={x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width)};}
          // cari grip: kotak 36-60px di bawah puzzle
          const all=[...document.querySelectorAll('*')];let best=null,bs=1e9;
          for(const e of all){const r=e.getBoundingClientRect();
            if(r.width>=34&&r.width<=60&&r.height>=34&&r.height<=60&&pz&&r.top>pz.getBoundingClientRect().bottom){
              if(r.x<bs){bs=r.x;best={x:Math.round(r.x),y:Math.round(r.y),cls:(e.className||'').toString().slice(0,40),tag:e.tagName};}}
          }
          g.grip=best; return g;}""")

    st0 = piece_state(); print("[before]", json.dumps(st0), flush=True)
    grip = st0.get("grip")
    if not grip:
        print("[diag] grip ga ketemu"); p.screenshot(path="/root/shopee-farm/shots/diag.png", full_page=True); time.sleep(3); c.close(); b.close(); sys.exit()
    sx, sy = grip["x"]+20, grip["y"]+20
    print(f"[diag] drag dari ({sx},{sy})", flush=True)

    # cara 1: page-level mouse
    p.mouse.move(sx, sy); p.mouse.down(); time.sleep(0.15)
    for i in range(1, 31):
        p.mouse.move(sx + i*7, sy + random.uniform(-1, 1)); time.sleep(0.02)
    p.mouse.up(); time.sleep(1.5)
    st1 = piece_state(); print("[after page-mouse]", json.dumps({k:st1.get(k) for k in ('piece','pieceStyle')}), flush=True)

    # cara 2: kalau ga gerak → dispatch ke elemen grip langsung
    if st1.get("piece") == st0.get("piece"):
        print("[diag] piece TIDAK gerak via page-mouse → coba dispatch ke elemen", flush=True)
        p.evaluate("""()=>{
          const all=[...document.querySelectorAll('*')];let g=null,bs=1e9;
          const pz=document.querySelector("aside canvas[draggable=false], #NEW_CAPTCHA canvas[draggable=false]");
          for(const e of all){const r=e.getBoundingClientRect();
            if(r.width>=34&&r.width<=60&&r.height>=34&&r.height<=60&&pz&&r.top>pz.getBoundingClientRect().bottom){if(r.x<bs){bs=r.x;g=e;}}}
          if(!g)return;
          const r=g.getBoundingClientRect();const x0=r.x+r.width/2,y0=r.y+r.height/2;
          const mk=(t,x)=>new MouseEvent(t,{bubbles:true,cancelable:true,view:window,clientX:x,clientY:y0,button:0,buttons:1});
          g.dispatchEvent(mk('mousedown',x0));
          document.dispatchEvent(mk('mousemove',x0));
          for(let i=0;i<40;i++){document.dispatchEvent(mk('mousemove',x0+i*5));}
          document.dispatchEvent(mk('mouseup',x0+200));
        }""")
        time.sleep(1.5)
        st2 = piece_state(); print("[after elem-dispatch]", json.dumps({k:st2.get(k) for k in ('piece','pieceStyle')}), flush=True)
    p.screenshot(path="/root/shopee-farm/shots/diag.png", full_page=True)
    time.sleep(3); c.close(); b.close()
