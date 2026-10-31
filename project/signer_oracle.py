#!/usr/bin/env python3
"""signer_oracle.py — ORACLE signer: page-context minting + capture.

Setelah VM ter-identifikasi (bytecode observable, 91 opcode traced), cara PALING
PASTI memakai signer = biarkan VM menghasilkan header di halaman, lalu tangkap.
Ini "oracle" — bukan reverse algoritma, tapi pakai VM-nya sebagai black-box
(bukti: x-sap-ri/sec terbentuk). Di luar boundary skill (bukan standalone signer).

Dua mode:
  A. capture: jalankan aksi apa pun di page live → record header x-sap-*.
  B. replay-test: pakai header yang di-capture untuk request (dalam sesi sama).
"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285611112223"
SECONDS = 70
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/signer_oracle.json"

HOOK = r"""
(() => {
  if (window.__ORA__) return; window.__ORA__=true;
  window.__ORALOG__=[];
  const grab = (h) => { const o={}; try{ (h&&h.forEach)?h.forEach((v,k)=>{
    if(/x-sap|sz-token|af-ac|x-sz/i.test(k)) o[k]=String(v).slice(0,300); }):null; }catch(e){} return o; };
  const of=window.fetch;
  window.fetch=async function(...a){
    const url=(typeof a[0]==='string')?a[0]:(a[0]&&a[0].url);
    const r=await of(...a);
    try{ const sig=grab(a[1]&&a[1].headers); if(Object.keys(sig).length)
      window.__ORALOG__.push({url:String(url).slice(0,90), status:r.status, sig}); }catch(e){}
    return r;
  };
  const oo=XMLHttpRequest.prototype.send, os=XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open=function(m,u){ this.__u=u; return os.apply(this,arguments); };
  XMLHttpRequest.prototype.send=function(){
    try{ const sig=grab(this); if(Object.keys(sig).length)
      window.__ORALOG__.push({url:String(this.__u).slice(0,90), xhr:1, sig}); }catch(e){}
    return oo.apply(this,arguments);
  };
})();
"""

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox","--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage","--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server":"http://"+HOST,"username":USER,"password":PASS}, ignore_https_errors=False)
    p = c.new_page(); p.add_init_script(HOOK)
    print("[oracle] load..."); p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    try: p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=2000, force=True); time.sleep(2)
    except Exception: pass
    try:
        inp=p.locator("input[name='phone']").first
        if inp.count(): inp.click(timeout=4000); inp.type(PHONE.lstrip("62").lstrip("0"), delay=40)
    except Exception: pass
    time.sleep(1.5)
    for sel in ["button:has-text('BERIKUTNYA')","text=BERIKUTNYA"]:
        try:
            loc=p.locator(sel).first
            if loc.count():
                bb=loc.bounding_box()
                if bb:
                    p.mouse.move(bb["x"]+bb["width"]/2,bb["y"]+bb["height"]/2); time.sleep(0.15)
                    p.mouse.down(); time.sleep(0.08); p.mouse.up(); break
        except Exception: pass
    print(f"[oracle] tunggu {SECONDS}s..."); time.sleep(SECONDS)
    log=p.evaluate("()=>window.__ORALOG__||[]")
    b.close()

json.dump(log, open(OUT,"w"), indent=1)
print(f"\n[oracle] signed requests captured: {len(log)}")
seen=set()
for e in log:
    for k in (e.get("sig") or {}):
        if k not in seen:
            seen.add(k)
            print(f"  {k}: {e['sig'][k][:60]}")
print(f"[oracle] → {OUT}")
