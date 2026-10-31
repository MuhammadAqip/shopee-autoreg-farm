#!/usr/bin/env python3
"""sap_x25519_capture.py — tangkap X25519 keypair + shared secret + AES key SAP.

SAP pakai X25519 ECDH (deriveBits) utk tukar kunci → AES utk af-ac-enc-sz-token.
Hook crypto.subtle: generateKey, deriveBits, importKey, encrypt — rekam semua
byte (raw key, iv, plaintext hint). Kalau shared secret + AES key ketangkap,
af-ac-enc-sz-token bisa didekripsi.

Usage: sap_x25519_capture.py <phone> [--seconds 100]
"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285600000000"
SECONDS = 100
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/sap_x25519.json"

HOOK = r"""
(() => {
  if (window.__X2__) return; window.__X2__ = true;
  window.__XLOG__ = [];
  const hex = (b) => { try{ return Array.from(new Uint8Array(b)).map(x=>x.toString(16).padStart(2,'0')).join(''); }catch(e){ return null; } };
  const push = (o) => { try{ if(window.__XLOG__.length<600) window.__XLOG__.push(o); }catch(e){} };
  const cs = crypto && crypto.subtle;
  if (!cs) return;
  const wrap = (op) => {
    if (!cs[op]) return;
    const orig = cs[op].bind(cs);
    cs[op] = async function(...args){
      const info = {op};
      try {
        info.alg = args[0] && (args[0].name || String(args[0]));
        if (op === 'generateKey') info.usages = args[2];
        if (op === 'importKey') { info.fmt = args[0];
          const kd = args[1];
          if (kd instanceof ArrayBuffer) info.key_hex = hex(kd);
          else if (ArrayBuffer.isView(kd)) info.key_hex = hex(kd.buffer);
        }
        if (op === 'deriveBits') { info.alg2 = args[0] && args[0].name;
          if (args[2]) info.bits = args[2]; }
        if (op === 'encrypt') { info.iv = args[1] && hex(args[1].iv || args[1]);
          const d = args[2]; if (d instanceof ArrayBuffer) info.pt_len = d.byteLength;
          else if (ArrayBuffer.isView(d)) info.pt_len = d.byteLength; }
        if (op === 'decrypt') { info.iv = args[1] && hex(args[1].iv || args[1]); }
      } catch(e){ info.err = String(e); }
      const r = await orig(...args);
      try {
        if (r && r.byteLength !== undefined) { info.res_len = r.byteLength; info.res_hex = hex(r); }
        else if (r && r.type) { info.res_type = r.type; info.res_usages = r.usages; }
      } catch(e){}
      push(info);
      return r;
    };
  };
  ['generateKey','importKey','deriveBits','deriveKey','encrypt','decrypt','sign','digest'].forEach(wrap);
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
    print("[x25519] load + trigger...")
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
    print(f"[x25519] tunggu {SECONDS}s..."); time.sleep(SECONDS)
    data = p.evaluate("()=>window.__XLOG__||[]")
    b.close()

json.dump(data, open(OUT, "w"), indent=1)
from collections import Counter
cnt = Counter((d.get("op"), d.get("alg") or d.get("alg2") or "") for d in data)
print(f"\n[x25519] total ops: {len(data)}")
for k, v in cnt.most_common(15):
    print(f"   {str(k[0]):12} {str(k[1])[:22]:22} x{v}")
keyed = [d for d in data if d.get("key_hex")]
print(f"[x25519] ops dgn raw key: {len(keyed)}")
for d in keyed[:6]:
    print(f"   {d.get('op')} fmt={d.get('fmt')} key={str(d.get('key_hex'))[:48]}")
print(f"[x25519] → {OUT}")
