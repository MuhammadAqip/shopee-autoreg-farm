#!/usr/bin/env python3
"""b2_headless.py — B2: uji apakah captcha Shopee bisa render+solve di HEADLESS (browser tipis).
Coba: chromium new-headless → signup → captcha → cek canvas ada & bisa di-drag.
"""
import sys, time, json, random
from playwright.sync_api import sync_playwright
import local_solver as LS

PHONE = sys.argv[1] if len(sys.argv) > 1 else "85729884046"
PROXY = open("/root/shopee-farm/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with sync_playwright() as pw:
    # B2: headless=True (new headless = chromium headless shell modern)
    b = pw.chromium.launch(headless=True, args=[
        "--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader", "--enable-webgl",
    ])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server":"http://"+HOST,"username":USER,"password":PASS},
                      ignore_https_errors=True, viewport={"width":1280,"height":900})
    c.add_cookies([{"name":"shopee_webLanguage","value":"id","domain":".shopee.co.id","path":"/"}])
    p = c.new_page()
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    try:
        p.wait_for_selector("input[name='phone']", timeout=45000)
    except Exception as e:
        print("[B2] input phone ga muncul:", str(e)[:80]); b.close(); sys.exit(1)
    time.sleep(4)
    try:
        mb=p.locator("button.shopee-button-outline").first
        if mb.count() and mb.is_visible(): mb.click(timeout=2500,force=True); time.sleep(3)
    except Exception: pass
    inp=p.locator("input[name='phone']").first; inp.click(timeout=5000); inp.type(PHONE,delay=45); time.sleep(4)
    for lbl in ("BERIKUTNYA","Berikutnya"):
        try: p.locator(f"button:has-text('{lbl}')").first.click(timeout=3000,force=True); break
        except Exception: pass
    time.sleep(3)
    for i in range(8):
        ok=p.evaluate("""()=>{const t=[...document.querySelectorAll('button,a,div')].reverse().find(e=>{const x=(e.innerText||'').trim();return x==='Setuju'||x==='SETUJU';});if(t){t.click();return true;}return false;}""")
        if ok: time.sleep(3); break
        time.sleep(2)
    rendered=False
    for i in range(50):
        time.sleep(1.5)
        cs=p.evaluate("()=>[...document.querySelectorAll('canvas')].map(c=>({w:c.width,h:c.height,d:c.getAttribute('draggable')}))")
        if cs: rendered=True; print("[B2] canvas muncul di headless:", cs); break
    if not rendered:
        body=p.evaluate("()=>document.body.innerText||''")
        print("[B2] ❌ captcha TIDAK render di headless. body:", body[:200].replace("\n"," | "))
        p.screenshot(path="/root/shopee-farm/shots/b2_headless.png")
    else:
        # coba ambil puzzle+piece (bukti pixel kebaca di headless)
        info=p.evaluate("""()=>{const pz=document.querySelector("aside canvas[draggable=false], #NEW_CAPTCHA canvas[draggable=false]");
          const pc=document.querySelector("aside canvas[draggable=true], #NEW_CAPTCHA canvas[draggable=true]");
          const o={};if(pz){o.puzzle=pz.toDataURL('image/png').split(',')[1];o.pw=pz.getBoundingClientRect().width;}
          if(pc){o.piece=pc.toDataURL('image/png').split(',')[1];}
          return o;}""")
        if info.get("puzzle"):
            xs,dbg=LS.candidates(info["puzzle"], info["piece"], topk=3)
            print("[B2] ✅ puzle kepencet di headless, kandidat:", xs)
            p.screenshot(path="/root/shopee-farm/shots/b2_headless.png")
            print("[B2] HASIL: headless CAN render + read puzzle (B2 viable)")
        else:
            print("[B2] canvas ada tapi pixel ga kebaca")
    time.sleep(2); c.close(); b.close()
