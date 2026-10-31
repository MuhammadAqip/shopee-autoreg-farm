#!/usr/bin/env python3
"""find_input.py — dump semua input element di halaman signup + fill nomor trial.
"""
import sys, time
from playwright.sync_api import sync_playwright
PHONE = sys.argv[1] if len(sys.argv) > 1 else "6285849156988"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://127.0.0.1:8888"}, ignore_https_errors=True,
                      viewport={"width": 1280, "height": 900})
    p = c.new_page()
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(6)
    info = p.evaluate("""()=>{
      const out=[];
      document.querySelectorAll('input').forEach((e,i)=>{
        const r=e.getBoundingClientRect();
        out.push({i, type:e.type, name:e.name, ph:e.placeholder||'', cls:e.className.slice(0,60),
                  x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height)});
      });
      return out;}""")
    print("[INPUTS]", flush=True)
    for x in info: print("  ", x, flush=True)
    # coba isi via JS + klik
    ok = p.evaluate("""(ph)=>{
      const inp=document.querySelector('input');
      if(!inp) return false;
      inp.focus();
      const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
      setter.call(inp, ph);
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));
      return true;}""", PHONE)
    print("[fill via JS]", ok, flush=True)
    time.sleep(2)
    # klik
    for label in ("BERIKUTNYA", "Berikutnya", "Lanjut"):
        try:
            p.locator(f"button:has-text('{label}')").first.click(timeout=2000, force=True)
            print(f"[klik] {label}", flush=True); break
        except Exception: pass
    time.sleep(8)
    body = p.evaluate("()=>document.body.innerText||''")
    print("[PAGE]", body[:400].replace("\n"," | "), flush=True)
    p.screenshot(path="/root/shopee-farm/shots/find_input.png", full_page=True)
    time.sleep(20)
    b.close()
