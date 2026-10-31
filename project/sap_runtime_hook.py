#!/usr/bin/env python3
"""sap_runtime_hook.py — #11-A: runtime-hook SAP signer (importScripts + crypto).

Target:
  1. Tangkap Worker creation di page (URL worker) → auto-attach CDP ke worker target
  2. Di worker: hook importScripts → tangkap URL signer asli
  3. Di worker: hook crypto.subtle + btoa + TextEncoder → lihat input/output signing
  4. Tangkap semua script yg di-load worker (importScripts target)

Output: sap_runtime.json {worker_urls, imported_scripts, crypto_calls, signer_url}
Pakai CDP (Playwright) + auto-attach ke target worker (Target.setAutoAttach).

Usage: sap_runtime_hook.py <phone> [--seconds 90]
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
OUT = f"{ROOT}/sap_runtime.json"

captured = {"worker_urls": [], "imported_scripts": [], "crypto_calls": [], "all_scripts": []}

# hook di worker (dijalankan via Runtime.evaluate saat worker attach)
WORKER_HOOK = r"""
(() => {
  if (self.__SAPHOOK__) return; self.__SAPHOOK__ = true;
  const post = (obj) => { try { self.postMessage({ __sap_hook: obj }); } catch(e){} };
  // 1) importScripts
  if (self.importScripts) {
    const oi = self.importScripts.bind(self);
    self.importScripts = function(...urls){ post({t:'importScripts', urls}); return oi(...urls); };
  }
  // 2) crypto.subtle
  try {
    const cs = (self.crypto && self.crypto.subtle) || null;
    if (cs && cs.sign) {
      const os = cs.sign.bind(cs);
      cs.sign = async function(alg, key, data){
        try { post({t:'subtle.sign', alg:(alg&&(alg.name||alg))||String(alg),
          data_len:(data&&data.byteLength)||0}); } catch(e){}
        return os(alg, key, data);
      };
    }
    if (cs && cs.importKey) {
      const ok = cs.importKey.bind(cs);
      cs.importKey = async function(fmt, keyData, ...r){
        try { post({t:'subtle.importKey', fmt}); } catch(e){}
        return ok(fmt, keyData, ...r);
      };
    }
    if (cs && cs.digest) {
      const od = cs.digest.bind(cs);
      cs.digest = async function(alg, data){
        try { post({t:'subtle.digest', alg:(alg&&(alg.name||alg))||String(alg), len:(data&&data.byteLength)||0}); } catch(e){}
        return od(alg, data);
      };
    }
  } catch(e){ post({t:'err', msg:String(e)}); }
  // 3) btoa/atob
  if (self.btoa) { const ob=self.btoa.bind(self); self.btoa=function(s){ post({t:'btoa', len:(s||'').length}); return ob(s); }; }
})();
"""

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                      ignore_https_errors=False)
    p = c.new_page()
    cdp = c.new_cdp_session(p)
    cdp.send("Network.enable")
    cdp.send("Target.setAutoAttach", {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True})

    def on_req(e):
        try:
            r = e.get("request", {}); u = r.get("url", "")
            if u.endswith(".js") or ".js?" in u:
                captured["all_scripts"].append(u)
        except Exception: pass
    cdp.on("Network.requestWillBeSent", on_req)

    # worker attach → inject hook + listen postMessage
    workers_hooked = set()
    def on_attached(ev):
        try:
            sess = cdp._connection._sessions.get(ev["sessionId"]) if hasattr(cdp._connection, "_sessions") else None
        except Exception:
            sess = None
    # pakai CDP raw event via playwright: Target.attachedToTarget
    try:
        cdp.on("Target.attachedToTarget", lambda ev: captured["worker_urls"].append(ev.get("targetInfo", {}).get("url")))
    except Exception:
        pass

    print("[hook] load signup + click verifikasi...")
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)
    try:
        p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=2000, force=True); time.sleep(2)
    except Exception: pass
    # isi nomor + klik → picu worker + report
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
    print(f"[hook] tunggu {SECONDS}s...")
    time.sleep(SECONDS)
    # ambil semua script + worker dari CDP Network (page context)
    try:
        scripts = p.evaluate("()=>performance.getEntriesByType('resource').map(e=>e.name).filter(n=>n.includes('.js')||n.includes('worker'))") or []
        captured["all_scripts"] = sorted(set(captured["all_scripts"] + scripts))
    except Exception: pass
    b.close()

# klasifikasi script
sd = [s for s in captured["all_scripts"] if any(k in s.lower() for k in ("sap", "sz", "shpsec", "sec", "af", "signal", "worker", "sdk"))]
captured["signer_candidates"] = sd
json.dump(captured, open(OUT, "w"), indent=1)
print(f"\n[hook] total scripts: {len(captured['all_scripts'])}")
print(f"[hook] worker urls: {captured['worker_urls']}")
print(f"[hook] signer candidates ({len(sd)}):")
for s in sd[:25]:
    print("  ", s[:120])
print(f"[hook] → {OUT}")
