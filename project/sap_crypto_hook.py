#!/usr/bin/env python3
"""sap_crypto_hook.py — #11-A: instrumentasi crypto.subtle di page + worker.

Sasaran: lihat operasi sign/digest/importKey saat SAP worker tanda tangan request.
Kalau SAP pakai crypto.subtle (WebCrypto), kita tangkap:
  - nama algoritma (HMAC/SHA-256/ECDSA/RSA)
  - panjang data & KEY (importKey raw)
  - hasil sign
→ rekonstruksi signature in-Python kalau algoritmanya standar.

Kalau SAP pakai WASM/embeded key (bukan subtle), bakal ketahuan dari hasil:
  crypto_calls kosong → berarti pakai kripto internal (WASM) → arah beda.

Usage: sap_crypto_hook.py <phone> [--seconds 90]
"""
import sys, os, time, json
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
OUT = f"{ROOT}/sap_crypto.json"

# JS hook: bungkus crypto.subtle + TextEncoder + btoa, catat ke __CRYPTO__ + Runtime binding
HOOK_JS = r"""
(() => {
  if (self.__CRYPTOHOOK__) return; self.__CRYPTOHOOK__ = true;
  const rec = (o) => { try { self.__CRYPTO__ = self.__CRYPTO__ || []; 
    if (self.__CRYPTO__.length < 500) self.__CRYPTO__.push(o);
    if (self.__sapBind) self.__sapBind(JSON.stringify(o)); } catch(e){} };
  const cs = self.crypto && self.crypto.subtle;
  if (cs) {
    ['sign','verify','digest','importKey','deriveBits','encrypt','decrypt'].forEach(op => {
      if (!cs[op]) return;
      const orig = cs[op].bind(cs);
      cs[op] = async function(...args) {
        let info = {op, alg: (args[0] && (args[0].name || args[0])) || String(args[0])};
        try {
          if (op === 'importKey') {
            const kd = args[1];
            if (kd && kd.byteLength !== undefined) { info.key_len = kd.byteLength;
              info.key_hex = Array.from(new Uint8Array(kd)).slice(0,64).map(b=>b.toString(16).padStart(2,'0')).join(''); }
            info.fmt = args[0]; info.usages = args[3];
          } else if (op === 'sign' || op === 'verify') {
            const d = args[2]; info.data_len = d && d.byteLength;
            if (d && d.byteLength !== undefined && d.byteLength < 256)
              info.data_hex = Array.from(new Uint8Array(d)).slice(0,64).map(b=>b.toString(16).padStart(2,'0')).join('');
          } else if (op === 'digest') {
            const d = args[1]; info.data_len = d && d.byteLength;
          }
        } catch(e){ info.err = String(e); }
        const res = await orig(...args);
        try {
          if (res && res.byteLength !== undefined) {
            info.res_len = res.byteLength;
            info.res_hex = Array.from(new Uint8Array(res)).slice(0,48).map(b=>b.toString(16).padStart(2,'0')).join('');
          }
        } catch(e){}
        rec(info);
        return res;
      };
    });
  }
})();
"""

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader", "--enable-features=SharedArrayBuffer"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                      ignore_https_errors=False)
    p = c.new_page()
    p.add_init_script(HOOK_JS + "\n;try{self.__sapBind=null;}catch(e){}")
    cdp = c.new_cdp_session(p)
    # auto-attach ke worker → inject hook di sana juga
    cdp.send("Target.setAutoAttach", {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True})
    cdp.send("Runtime.enable")
    try:
        cdp.send("Runtime.addBinding", {"name": "__sapBind"})
    except Exception:
        pass

    crypto_events = {"page": [], "workers": []}
    def on_binding(ev):
        try:
            crypto_events["page"].append(json.loads(ev.get("payload", "{}")))
        except Exception: pass
    try:
        cdp.on("Runtime.bindingCalled", on_binding)
    except Exception: pass

    print("[crypto] load signup + trigger...")
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
    print(f"[crypto] tunggu {SECONDS}s...")
    time.sleep(SECONDS)
    try:
        crypto_events["page"] = crypto_events["page"] + (p.evaluate("()=>window.__CRYPTO__||[]") or [])
    except Exception: pass
    b.close()

json.dump(crypto_events, open(OUT, "w"), indent=1)
calls = crypto_events["page"]
print(f"\n[crypto] total crypto ops (page): {len(calls)}")
seen = {}
for c in calls:
    k = (c.get("op"), c.get("alg"))
    seen[k] = seen.get(k, 0) + 1
for k, v in sorted(seen.items(), key=lambda x: -x[1]):
    print(f"   {k[0]:10} {str(k[1])[:30]:30} x{v}")
keyed = [c for c in calls if c.get("key_hex")]
print(f"[crypto] importKey dgn raw key: {len(keyed)}")
for c in keyed[:5]:
    print("   key_len=", c.get("key_len"), "fmt=", c.get("fmt"), "hex=", (c.get("key_hex") or "")[:48])
print(f"[crypto] → {OUT}")
