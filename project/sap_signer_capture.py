#!/usr/bin/env python3
"""sap_signer_capture.py — tangkap x-sap-sec runtime + sadap fungsi sign.

Strategi (karena signer di VM-obfuscate):
  1. Hook fetch + XHR: catat SEMUA header x-sap-* / sz-token / af-ac-* per request
  2. Hook Web Crypto subtle (kalau dipakai)
  3. Hook module 30914 (SAP SDK) — kalau bisa, bungkus method-nya utk lihat input/output
  4. Simpan pasangan (request url, payload hash) ↔ (x-sap-ri, x-sap-sec, sz-token)

Tujuan: pahami APA yg di-sign + apakah bisa dipalsukan.

Usage: sap_signer_capture.py <phone> [--seconds 90]
"""
import sys, os, time, json, base64, hashlib
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285600000000"
SECONDS = 90
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/sap_signer.json"

HOOK = r"""
(() => {
  if (window.__SAPSIG__) return; window.__SAPSIG__ = true;
  window.__SIG__ = [];
  const rec = (o) => { try { if (window.__SIG__.length < 800) window.__SIG__.push(o); } catch(e){} };
  const grab = (h) => {
    try {
      const g = (k) => h && (h[k] || h[k.toLowerCase()] || h[k.toUpperCase()]);
      return { 'x-sap-ri': g('x-sap-ri'), 'x-sap-sec': g('x-sap-sec'),
               'x-sap-ri-rid': g('x-sap-ri-rid'), 'af-ac-enc-sz-token': g('af-ac-enc-sz-token'),
               'af-ac-enc-dat': g('af-ac-enc-dat'), 'sz-token': g('sz-token'),
               'x-sz-sdk-version': g('x-sz-sdk-version'),
               'device_sz_fingerprint': g('device_sz_fingerprint') };
    } catch(e){ return {}; }
  };
  const of = window.fetch;
  window.fetch = function(a, b){
    try {
      const url = (a && a.url) || String(a);
      let hdrs = (b && b.headers) || (a && a.headers) || {};
      if (hdrs && typeof hdrs.forEach === 'function') { const o={}; hdrs.forEach((v,k)=>o[k]=v); hdrs=o; }
      const sig = grab(hdrs);
      if (sig['x-sap-ri'] || sig['sz-token'] || url.includes('/api/v4/')) {
        let bodyHash=null;
        try { if (b && b.body && b.body.byteLength) bodyHash = 'len:'+b.body.byteLength; } catch(e){}
        rec({kind:'fetch', url: url.split('?')[0], sig, bodyHash});
      }
    } catch(e){}
    return of.apply(this, arguments);
  };
  const oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send, osh=XMLHttpRequest.prototype.setRequestHeader;
  XMLHttpRequest.prototype.open=function(m,u){this.__u=u;this.__h={};return oo.apply(this,arguments);};
  XMLHttpRequest.prototype.setRequestHeader=function(k,v){try{this.__h[k]=v;}catch(e){}return osh.apply(this,arguments);};
  XMLHttpRequest.prototype.send=function(b){
    try{
      const sig=grab(this.__h);
      if(sig['x-sap-ri']||sig['sz-token']||(this.__u||'').includes('/api/v4/')){
        rec({kind:'xhr', url:(this.__u||'').split('?')[0], sig});
      }
    }catch(e){}
    return os.apply(this,arguments);
  };
  // hook subtle (kalau signer pakai)
  try{
    const cs = crypto.subtle;
    ['sign','digest','encrypt'].forEach(op=>{
      if(!cs[op])return; const o=cs[op].bind(cs);
      cs[op]=async function(){ let info={kind:'subtle', op, alg:(arguments[0]&&(arguments[0].name||arguments[0]))||''};
        try{ const r=await o.apply(cs,arguments); if(r&&r.byteLength) info.res_len=r.byteLength; }catch(e){}
        rec(info); return arguments.length? (await o.apply(cs,arguments)) : undefined; };
    });
  }catch(e){}
})();
"""

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                      ignore_https_errors=False)
    p = c.new_page()
    p.add_init_script(HOOK)
    print("[sig] load signup + trigger...")
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)
    try:
        p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=2000, force=True); time.sleep(2)
    except Exception: pass
    try:
        inp = p.locator("input[name='phone']").first
        if inp.count():
            inp.click(timeout=4000); inp.type(PHONE.lstrip("62").lstrip("0"), delay=40)
    except Exception: pass
    time.sleep(1.5)
    for sel in ["button:has-text('BERIKUTNYA')", "text=BERIKUTNYA"]:
        try:
            loc = p.locator(sel).first
            if loc.count():
                bb = loc.bounding_box()
                if bb:
                    p.mouse.move(bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2); time.sleep(0.15)
                    p.mouse.down(); time.sleep(0.08); p.mouse.up(); break
        except Exception: pass
    print(f"[sig] tunggu {SECONDS}s...")
    time.sleep(SECONDS)
    data = p.evaluate("()=>window.__SIG__||[]")
    b.close()

json.dump(data, open(OUT, "w"), indent=1)
sapped = [d for d in data if d.get("sig", {}).get("x-sap-ri")]
print(f"\n[sig] events: {len(data)} | with x-sap-ri: {len(sapped)}")
for d in sapped[:6]:
    s = d["sig"]
    print(f"  {d['url'][-45:]:45} ri={str(s.get('x-sap-ri'))[:24]} sec_len={len(s.get('x-sap-sec') or '')}")
    if s.get("sz-token"): print(f"      sz-token={str(s['sz-token'])[:40]}")
    if s.get("af-ac-enc-sz-token"): print(f"      af-ac-enc-sz-token={str(s['af-ac-enc-sz-token'])[:40]}")
print(f"[sig] → {OUT}")
