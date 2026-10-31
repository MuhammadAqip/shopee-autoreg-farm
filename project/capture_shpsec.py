#!/usr/bin/env python3
"""capture_shpsec.py — tangkap body BINARY dari POST /v2/shpsec/web/report + decrypt.

Hook fetch + XHR: simpan body (ArrayBuffer/base64) ke window.__SHP__,
lalu decrypt pakai sense_decrypt.

Usage: capture_shpsec.py <phone> [--seconds 90]
"""
import sys, os, time, json, base64
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
OUT = f"{ROOT}/shpsec_body.bin"

HOOK = r"""
(() => {
  window.__SHP__ = [];
  const toB64 = (buf) => { try{ let b=new Uint8Array(buf); let s=''; for(let i=0;i<b.length;i++) s+=String.fromCharCode(b[i]); return btoa(s);}catch(e){return null;} };
  const of = window.fetch;
  window.fetch = async function(a, b){
    try{
      const url = (a && a.url) || String(a);
      let body = (b && b.body) || (a && a.body);
      if (url.includes('shpsec/web/report')){
        if (body instanceof ArrayBuffer){ window.__SHP__.push({kind:'fetch', b64: toB64(body)}); }
        else if (body instanceof Blob){ body.arrayBuffer().then(ab=>window.__SHP__.push({kind:'fetch-blob', b64: toB64(ab)})); }
        else if (body && body.byteLength){ window.__SHP__.push({kind:'fetch-typed', b64: toB64(body.buffer||body)}); }
        else if (typeof body === 'string'){ window.__SHP__.push({kind:'fetch-str', str: body.slice(0,4000)}); }
      }
    }catch(e){}
    return of.apply(this, arguments);
  };
  const oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(m,u){ this.__u=u; return oo.apply(this,arguments); };
  XMLHttpRequest.prototype.send = function(body){
    try{
      if ((this.__u||'').includes('shpsec/web/report') && body){
        let b64=null;
        if (body instanceof ArrayBuffer) b64 = toB64(body);
        else if (body && body.buffer) b64 = toB64(body.buffer);
        else if (typeof body === 'string') { window.__SHP__.push({kind:'xhr-str', str: body.slice(0,4000)}); }
        if (b64) window.__SHP__.push({kind:'xhr', b64});
      }
    }catch(e){}
    return os.apply(this,arguments);
  };
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
    print("[shp] load signup + trigger captcha/report...")
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
    print(f"[shp] tunggu {SECONDS}s...")
    time.sleep(SECONDS)
    data = p.evaluate("()=>window.__SHP__||[]")
    b.close()

bodies = []
for d in data:
    if d.get("b64"):
        bodies.append((d.get("kind"), base64.b64decode(d["b64"])))
    elif d.get("str"):
        bodies.append((d.get("kind"), d["str"].encode("latin1")))

print(f"\n[shp] bodies: {len(bodies)}")
if bodies:
    kind, raw = bodies[0]
    open(OUT, "wb").write(raw)
    print(f"[shp] {kind} len={len(raw)} head={raw[:16].hex()} → {OUT}")

# decrypt
try:
    import sense_decrypt as S
    for kind, raw in bodies[:3]:
        r = S.parse_payload(raw)
        print(f"  {kind}: ver={r.get('version')} crc_ok={r.get('crc_ok')} len_ev={r.get('len_events')} err={r.get('decrypt_err','')}")
except Exception as e:
    print("[shp] decrypt skip:", e)
