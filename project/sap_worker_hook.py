#!/usr/bin/env python3
"""sap_worker_hook.py — #11-A: attach CDP ke worker SAP → tangkap importScripts (rule sets).

Worker af388a21...worker.js memanggil importScripts(<ruleSetName>) utk load modul
kripto dinamis. Kita attach ke target worker (Target.setAutoAttach) dan inject hook
self.importScripts utk tangkap nama/URL rule set → download → analisa aturan sign.

Usage: sap_worker_hook.py <phone> [--seconds 90]
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
OUT = f"{ROOT}/sap_workers.json"

WORKER_INJECT = r"""
(() => {
  if (self.__WH__) return; self.__WH__ = true;
  const oi = self.importScripts && self.importScripts.bind(self);
  if (oi) self.importScripts = function(...u){ try{ self.postMessage({__w:"importScripts", urls:u}); }catch(e){} return oi(...u); };
  // rule set loader: self.importScripts(t) dgn t = nama rule set
  self.addEventListener('message', (e)=>{ try{ self.postMessage({__w:"msg", data:String(e.data).slice(0,300)}); }catch(x){} });
})();
"""


def attach_and_inject(cdp_session, target_id, log):
    """Inject hook ke worker target via CDP session."""
    def _on(ev):
        log(f"[worker] attached: {ev.get('targetInfo',{}).get('type')} {ev.get('targetInfo',{}).get('url','')[:70]}")


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                      ignore_https_errors=False)
    p = c.new_page()
    cdp = c.new_cdp_session(p)
    cdp.send("Target.setAutoAttach", {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True})
    cdp.send("Network.enable")

    import_scripts = []
    worker_urls = []

    # Network: tangkap .js yg di-import worker (rule set)
    def on_req(e):
        try:
            u = e.get("request", {}).get("url", "")
            if "rule" in u.lower() or "sap" in u.lower() or "sz" in u.lower() or u.endswith(".js"):
                import_scripts.append(u)
        except Exception: pass
    cdp.on("Network.requestWillBeSent", on_req)

    # cara paling andal: pakai CDP langsung via raw session utk worker
    # Playwright: setiap worker target muncul sebagai page.on('worker')
    def on_worker(w):
        try:
            worker_urls.append(w.url)
            print(f"[worker] NEW: {w.url[:90]}")
            # inject via evaluate di worker context
            w.evaluate(WORKER_INJECT)
            w.on("console", lambda m: None)
        except Exception as e:
            print(f"[worker] inject err {str(e)[:70]}")
    p.on("worker", on_worker)

    print("[wk] load signup + trigger...")
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
    # trigger captcha → yang picu report/sign
    print(f"[wk] tunggu {SECONDS}s (workers akan attach)...")
    time.sleep(SECONDS)
    # capture network js lagi
    try:
        res = p.evaluate("()=>performance.getEntriesByType('resource').map(e=>e.name)") or []
        for u in res:
            if u.endswith(".js") and (u not in import_scripts):
                import_scripts.append(u)
    except Exception: pass
    b.close()

import_scripts = sorted(set(import_scripts))
rules = [u for u in import_scripts if any(k in u.lower() for k in ("rule", "sap", "/sz", "shpsec", "crypto", "sign"))]
json.dump({"worker_urls": worker_urls, "rule_candidates": rules, "all_js": import_scripts[:200]},
          open(OUT, "w"), indent=1)
print(f"\n[wk] workers seen: {worker_urls}")
print(f"[wk] rule/crypto candidates ({len(rules)}):")
for u in rules[:30]:
    print("  ", u[:130])
print(f"[wk] → {OUT}")
