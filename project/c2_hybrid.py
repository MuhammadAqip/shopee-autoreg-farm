#!/usr/bin/env python3
"""c2_hybrid.py — C2: browser (headless) solve captcha → sedot security_data SEGAR dari
response verify_v2 → langsung tembak send_vcode via requests (API-driven, bukan page).

Bukti arsitektur: browser HANYA buat captcha; pengiriman WA murni API.
Usage: c2_hybrid.py <PHONE>
"""
import sys, time, json, random
import requests
from playwright.sync_api import sync_playwright
import local_solver as LS
from shopee_hold import solve_image_crawl  # reuse solver yg terbukti

ROOT = "/root/shopee-farm"
PHONE = sys.argv[1] if len(sys.argv) > 1 else "85729884047"
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LOG = open(f"{ROOT}/capture/c2_flow.jsonl", "a")
CAP = {"verify": None, "api_done": False}
CK = {}          # cookies browser (diisi setelah context siap)
SREQ = None      # requests session
def rec(d): LOG.write(json.dumps(d, ensure_ascii=False)+"\n"); LOG.flush()

def fire_api(ch3=True):
    """Tembak send_vcode via requests pakai security_data segar + cookies browser."""
    if CAP["api_done"] or not CAP["verify"] or not CK:
        return
    CAP["api_done"] = True
    s = requests.Session()
    s.headers.update({"User-Agent":UA,"accept":"application/json","content-type":"application/json",
        "x-api-source":"pc","x-requested-with":"XMLHttpRequest","x-shopee-language":"id",
        "referer":"https://shopee.co.id/buyer/signup","x-csrftoken":CK.get("csrftoken","")})
    for k,v in CK.items():
        try: s.cookies.set(k,v,domain=".shopee.co.id")
        except Exception: pass
    s.proxies={"http":PROXY,"https":PROXY}
    body={"channel":3 if ch3 else 1,"operation":8,"phone":PHONE,"m_token":CAP["verify"],
          "supported_channels":[1,2,3,6,0,5],
          "client_identifier":{"security_device_fingerprint":CK.get("_sapid","")}}
    try:
        r=s.post("https://shopee.co.id/api/v4/otp/send_vcode", json=body, timeout=30)
        print(f"[C2] ★ send_vcode API(ch3,op8) {r.status_code} → {r.text[:200]}", flush=True)
    except Exception as e:
        print("[C2] send_vcode ERR", str(e)[:100], flush=True)

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=[
        "--no-sandbox", "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage", "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server":"http://"+HOST,"username":USER,"password":PASS},
                      ignore_https_errors=True, viewport={"width":1280,"height":900})
    c.add_cookies([{"name":"shopee_webLanguage","value":"id","domain":".shopee.co.id","path":"/"}])
    p = c.new_page()
    held={}
    def on_req(r):
        u=r.url
        if any(k in u for k in ("captcha","anti_fraud","otp","vcode")): held[r]={"m":r.method,"u":u,"b":r.post_data or ""}
    def on_resp(r):
        if r.request in held:
            e=dict(held[r.request]); e["s"]=r.status
            try: e["r"]=(r.text() or "")[:2500]
            except Exception: e["r"]=""
            rec(e)
            if "verify_v2" in e["u"] and e["s"]==200:
                try: CAP["verify"]=json.loads(e["r"]).get("security_data")
                except Exception: pass
                print("[C2] sedot security_data segar:", (CAP["verify"] or "")[:50], flush=True)
                # ★ fire API SEGERA saat token landing (no race)
                try: fire_api()
                except Exception as _e: print("[C2] fire_api err", str(_e)[:80], flush=True)
    p.on("request",on_req); p.on("response",on_resp)

    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    p.wait_for_selector("input[name='phone']", timeout=45000); time.sleep(4)
    try:
        mb=p.locator("button.shopee-button-outline").first
        if mb.count() and mb.is_visible(): mb.click(timeout=2500,force=True); time.sleep(3)
    except Exception: pass
    inp=p.locator("input[name='phone']").first; inp.click(timeout=5000); inp.type(PHONE,delay=45); time.sleep(4)
    for lbl in ("BERIKUTNYA","Berikutnya"):
        try: p.locator(f"button:has-text('{lbl}')").first.click(timeout=3000,force=True); break
        except Exception: pass
    time.sleep(3)
    for i in range(8):
        ok=p.evaluate("""()=>{const t=[...document.querySelectorAll('button,a,div')].reverse().find(e=>{const x=(e.innerText||'').trim();return x==='Setuju'||x==='SETUJU';});if(t){t.click();return true;}return false;}""")
        if ok: time.sleep(3); break
        time.sleep(2)
    # tunggu captcha (sabar: sampai 90s, refresh kalau perlu)
    got=False
    for i in range(60):
        time.sleep(1.5)
        if p.evaluate("()=>!!document.querySelector('aside canvas[draggable=true], #NEW_CAPTCHA canvas[draggable=true]')"):
            got=True; print("[C2] captcha canvas terdeteksi", flush=True); break
    if not got:
        # klik BERIKUTNYA lagi / tunggu ekstra
        for lbl in ("BERIKUTNYA","Berikutnya"):
            try: p.locator(f"button:has-text('{lbl}')").first.click(timeout=2500,force=True); break
            except Exception: pass
        for i in range(40):
            time.sleep(1.5)
            if p.evaluate("()=>!!document.querySelector('aside canvas[draggable=true], #NEW_CAPTCHA canvas[draggable=true]')"):
                got=True; print("[C2] captcha canvas terdeteksi (retry)", flush=True); break
    for w in range(16):
        if "Memuat" not in p.evaluate("()=>document.body.innerText||''"): break
        time.sleep(1.5)
    # solve pakai solver terbukti (butuh key)
    KEY = open(f"{ROOT}/bot_key.txt").read().strip()
    res = solve_image_crawl(p, KEY)
    print("[C2] solve:", {k:res.get(k) for k in ('type','target','src')} if isinstance(res,dict) else res, flush=True)
    # simpan cookies browser (fresh) SEBELUM tunggu verify, biar fire_api siap
    CK.update({x["name"]:x["value"] for x in c.cookies()})
    print("[C2] cookies:", len(CK), flush=True)
    time.sleep(4)

    # tunggu fire_api selesai (verify_v2 → API call) max 60s
    for _w in range(60):
        if CAP["api_done"]:
            break
        time.sleep(1)
    if not CAP["api_done"] and CAP["verify"]:
        # fallback: verify landed tapi belum ke-fire
        CK.update({x["name"]:x["value"] for x in c.cookies()})
        fire_api()
    print("[C2] final: security_data=", (CAP["verify"] or "")[:30], "api_done=", CAP["api_done"], flush=True)
    body = p.evaluate("()=>document.body.innerText||''")
    print("[C2][PAGE]", body[:200].replace("\n"," | "), flush=True)
    p.screenshot(path=f"{ROOT}/shots/c2_hybrid.png")
    time.sleep(2); c.close(); b.close()
