#!/usr/bin/env python3
"""afac_handshake.py — trace handshake X25519 → AES key untuk af-ac-enc-sz-token.

Dua stub:
  A. Hook crypto.subtle.deriveBits + importKey untuk tangkap shared secret X25519
     + key mentah.
  B. Intercept POST /verify/traffic (request + response) → cari field kunci.
  C. Coba dekripsi af-ac-enc-sz-token pakai shared secret (KDF kandidat).
"""
import sys, os, time, json, base64, hashlib
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285600002222"
SECONDS = 90
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/afac_handshake.json"

HOOK = r"""
(() => {
  if (window.__AFA__) return; window.__AFA__ = true;
  window.__AFALOG__ = {derive:[], keys:[], verify:[]};
  const hex = (b) => { try{ return Array.from(new Uint8Array(b)).map(x=>x.toString(16).padStart(2,'0')).join(''); }catch(e){ return null; } };
  const b64 = (b) => { try{ return btoa(String.fromCharCode(...new Uint8Array(b))); }catch(e){ return null; } };
  // 1. hook subtle
  const cs = crypto && crypto.subtle;
  if (cs) {
    const odb = cs.deriveBits ? cs.deriveBits.bind(cs) : null;
    if (odb) cs.deriveBits = async function(...a){
      const alg = a[0]&&a[0].name;
      let pub=null; try{ pub = a[1] && (a[1].x ? b64(a[1].x) : null); }catch(e){}
      const r = await odb(...a);
      window.__AFALOG__.derive.push({alg, pub, secret_hex: hex(r), secret_b64: b64(r)});
      return r;
    };
    const oik = cs.importKey ? cs.importKey.bind(cs) : null;
    if (oik) cs.importKey = async function(...a){
      try { const d=a[1]; let raw=null;
        if (d instanceof ArrayBuffer) raw=b64(d); else if (ArrayBuffer.isView(d)) raw=b64(d.buffer);
        window.__AFALOG__.keys.push({fmt:a[0], alg:a[2]&&a[2].name, raw_b64:raw, usages:a[4]});
      } catch(e){}
      return oik(...a);
    };
  }
  // 2. hook fetch untuk /verify/traffic
  const of = window.fetch;
  window.fetch = async function(...a){
    const url = (typeof a[0]==='string')?a[0]:(a[0]&&a[0].url);
    const r = await of(...a);
    if (url && url.indexOf('/verify/traffic')>=0) {
      try { const t = await r.clone().text();
        window.__AFALOG__.verify.push({url, status:r.status, body:t.slice(0,2000),
          req_headers: (a[1]&&a[1].headers)?Object.fromEntries(new Headers(a[1].headers).entries()):{},
          req_body: (a[1]&&a[1].body)?String(a[1].body).slice(0,1000):null});
      } catch(e){}
    }
    return r;
  };
})();
"""

def kdf_candidates(secret):
    """KDF kandidat dari shared secret X25519 → AES key."""
    out = {}
    out["raw16"] = secret[:16]
    out["raw32"] = secret[:32]
    out["sha256"] = hashlib.sha256(secret).digest()
    out["sha256_16"] = hashlib.sha256(secret).digest()[:16]
    out["md5"] = hashlib.md5(secret).digest()
    out["hkdf"] = hashlib.sha256(secret + b"\x01").digest()[:16]
    return out

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                      ignore_https_errors=False)
    p = c.new_page()
    p.add_init_script(HOOK)
    print("[afac] load + trigger...")
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
    print(f"[afac] tunggu {SECONDS}s..."); time.sleep(SECONDS)
    data = p.evaluate("()=>window.__AFALOG__||{}")
    b.close()

json.dump(data, open(OUT, "w"), indent=1)
print(f"\n[afac] deriveBits ops: {len(data.get('derive',[]))}")
for d in data.get("derive",[])[:5]:
    print(f"   {d.get('alg')} pub={str(d.get('pub'))[:24]} secret={str(d.get('secret_hex'))[:40]}")
print(f"[afac] importKey ops: {len(data.get('keys',[]))}")
for k in data.get("keys",[])[:5]:
    print(f"   fmt={k.get('fmt')} alg={k.get('alg')} raw={str(k.get('raw_b64'))[:32]}")
print(f"[afac] verify/traffic calls: {len(data.get('verify',[]))}")
for v in data.get("verify",[])[:3]:
    print(f"   {v.get('status')} {v.get('url','')[:60]}")
    print(f"      req_body={str(v.get('req_body'))[:120]}")
    print(f"      resp={str(v.get('body'))[:160]}")
print(f"[afac] → {OUT}")
