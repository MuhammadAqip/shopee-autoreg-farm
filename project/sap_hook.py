#!/usr/bin/env python3
"""sap_hook.py — #11: SAP/anti-fraud reconnaissance + token capture.

Tujuan (reverse sz-sdk tanpa deobfuscate WASM):
  1. Tangkap riskToken dari /v2/shpsec/web/report (dari dalam page)
  2. Tangkap header x-sap-ri / x-sap-sec / af-ac-enc-sz-token yg SDK generate
     utk request apa pun
  3. Simpan ke sap_tokens.json → bisa dipakai "replay" (kalau token reusable
     dalam window singkat, mis. get_settings_v2/send_vcode)

Temuan recon (2026-10-16):
  - Worker: shopee.co.id/pcmall-assets/assets/af388a216703068c.worker.js
  - Report: POST df.infra.sz.shopee.co.id/v2/shpsec/web/report (payload BINARY/encrypted)
  - riskToken format: b64|b64|b64|08|<platform>
  - x-sap-ri/x-sap-sec: di-inject SDK per-request
  - Sourcemap: sourcemap.webfe.shopeemobile.com/... (UNREACHABLE)

Usage: sap_hook.py <phone> [--seconds 60]
"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285600000000"
SECONDS = 60
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OUT = f"{ROOT}/sap_tokens.json"


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                      ignore_https_errors=False)
    p = c.new_page()
    # hook XHR/fetch sebelum load
    p.add_init_script("""
      window.__SAP__ = {reports:[], sapped:[]};
      const of = window.fetch;
      window.fetch = async function(){
        const url = (arguments[0]&&arguments[0].url)||String(arguments[0]);
        const opts = arguments[1]||{};
        const r = await of.apply(this, arguments);
        try{
          if(url.includes('shpsec/web/report')){
            const cl=r.clone(); cl.json().then(j=>{ window.__SAP__.reports.push({url, resp:j}); }).catch(()=>{});
          }
          if(url.includes('/api/v4/')){
            const h = (opts.headers||{});
            window.__SAP__.sapped.push({url, ri:h['x-sap-ri']||h['X-Sap-Ri'], sec:h['x-sap-sec']||h['X-Sap-Sec'],
              sz:(h['af-ac-enc-sz-token']||h['af-ac-enc-dat'])});
          }
        }catch(e){}
        return r;
      };
      const oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
      XMLHttpRequest.prototype.open=function(m,u){this.__u=u;return oo.apply(this,arguments);};
      XMLHttpRequest.prototype.send=function(){
        const self=this;
        self.addEventListener('load',function(){
          try{
            const u=self.__u||'';
            if(u.includes('shpsec/web/report')){ const j=JSON.parse(self.responseText);
              window.__SAP__.reports.push({url:u, resp:j}); }
          }catch(e){}
        });
        return os.apply(this,arguments);
      };
    """)
    c_cdp = c.new_cdp_session(p)
    c_cdp.send("Network.enable")
    hdrs = {}
    def _on_req(e):
        try:
            r = e.get("request", {}); u = r.get("url", "")
            if "/api/v4/" in u:
                h = {k.lower(): v for k, v in (r.get("headers") or {}).items()}
                hdrs[e["requestId"]] = {"url": u, "x-sap-ri": h.get("x-sap-ri"),
                                        "x-sap-sec": h.get("x-sap-sec"),
                                        "af-ac-enc-sz-token": h.get("af-ac-enc-sz-token")}
        except Exception: pass
    c_cdp.on("Network.requestWillBeSent", _on_req)

    print("[sap] buka signup → picu report...")
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)
    try:
        p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=2000, force=True); time.sleep(2)
    except Exception: pass
    # isi nomor + klik BERIKUTNYA → picu shpsec/web/report (riskToken)
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
    print(f"[sap] tunggu {SECONDS}s utk report + headers...")
    time.sleep(SECONDS)
    data = p.evaluate("()=>window.__SAP__ || {}")
    b.close()

risktokens = [r for r in data.get("reports", []) if r.get("resp", {}).get("data", {}).get("riskToken")]
saps = [h for h in hdrs.values() if h.get("x-sap-ri")]
out = {"riskTokens": [r["resp"]["data"]["riskToken"] for r in risktokens],
       "sap_headers": saps[:10], "reports_raw": risktokens[:2]}
json.dump(out, open(OUT, "w"), indent=1)
print(f"\n[sap] riskToken diperoleh: {len(out['riskTokens'])}")
for rt in out["riskTokens"][:3]:
    print("  ", rt[:70], "...")
print(f"[sap] x-sap-ri headers: {len(saps)}")
for h in saps[:3]:
    print("  ", (h.get('url') or '')[-40:], "| ri:", (h.get('x-sap-ri') or '')[:20], "| sec:", (h.get('x-sap-sec') or '')[:20])
print(f"[sap] → {OUT}")
