#!/usr/bin/env python3
"""phone_checker.py — cek nomor FRESH / TERDAFTAR dari awal (sebelum captcha).

Metode: API `otp/get_settings_v2 {operation:8, phone}` (page-context, SDK-signed).
- available_channels mengandung 3 (whatsapp) → FRESH (nomor belum terdaftar, WA tersedia)
- available_channels == [1] (sms saja) → TERDAFTAR (nomor sudah punya akun)
- preferred_channel 3 → fresh WA
Plus: coba klik "BERIKUTNYA" → kalau langsung muncul "Apakah ini akunmu?" → terdaftar.

Usage:
  phone_checker.py 87876125616            # 1 nomor
  phone_checker.py --file numbers.txt     # batch
  phone_checker.py 8x,8y,8z               # multi koma
Output: phone_check.json {phone: {fresh:bool, channels:[], preferred:...}}
"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

ROOT = "/root/shopee-farm"
sys.path.insert(0, ROOT)
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def norm(p):
    p = p.strip().lstrip("+0")
    if not p.startswith("62"):
        p = "62" + p
    return p


def collect_phones():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    phones = []
    for a in args:
        if a.endswith(".txt") or "," in a:
            if a.endswith(".txt") and os.path.exists(a):
                phones += [x.strip() for x in open(a) if x.strip()]
            else:
                phones += [x.strip() for x in a.split(",") if x.strip()]
        else:
            phones.append(a)
    return [norm(p) for p in phones if p]


JS_CHECK = """async (args)=>{
  const post=async(u,b)=>{try{const r=await fetch(u,{method:'POST',credentials:'include',
    headers:{'Content-Type':'application/json','x-api-source':'pc','x-requested-with':'XMLHttpRequest'},
    body:JSON.stringify(b)});return {status:r.status,json:await r.json()};}catch(e){return {status:-1,err:String(e)};}};
  const cks=document.cookie.split('; ').reduce((a,c)=>{const i=c.indexOf('=');a[c.slice(0,i)]=c.slice(i+1);return a;},{});
  const fp=cks['shopee_webUnique_ccd']||args.fp||'';
  const r=await post('/api/v4/otp/get_settings_v2',{operation:8,phone:args.phone,
    supported_channels:[1,2,3,6,0,5],support_session:true,
    client_identifier:{security_device_fingerprint:fp}});
  return r;
}"""

# deteksi interstitial "sudah terdaftar" dari DOM (setelah klik BERIKUTNYA, sebelum captcha)
JS_INTERSTITIAL = """()=>{
  const t=(document.body.innerText||'');
  if(/sudah terdaftar di Shopee|Apakah ini akunmu/i.test(t)) return {registered:true, text:'registered'};
  if(/Verifikasi untuk melanjutkan|Geser untuk menyelesaikan puzzle|#NEW_CAPTCHA/i.test(t)) return {registered:false, text:'captcha'};
  return {registered:null, text:t.slice(0,80)};
}"""


def dom_check(p, ph, FP):
    """Klik BERIKUTNYA utk nomor → deteksi interstitial (registered) vs captcha (fresh)."""
    p.evaluate("(v)=>{try{document.cookie='shopee_webUnique_ccd='+v+'; path=/; domain=.shopee.co.id';}catch(e){}}", FP)
    # isi nomor
    try:
        inp = p.locator("input[name='phone']").first
        if inp.count():
            inp.click(timeout=4000)
            inp.fill("")
            inp.type(ph.replace("62", "", 1), delay=40)  # form minta tanpa 62
    except Exception:
        pass
    time.sleep(1.2)
    # klik BERIKUTNYA
    for sel in ["button:has-text('BERIKUTNYA')", "button:has-text('Berikutnya')", "text=BERIKUTNYA"]:
        try:
            loc = p.locator(sel).first
            if loc.count():
                bb = loc.bounding_box()
                if bb:
                    p.mouse.move(bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2); time.sleep(0.15)
                    p.mouse.down(); time.sleep(0.08); p.mouse.up(); break
        except Exception:
            pass
    time.sleep(4)
    # setuju TOS kalau ada
    for _ in range(4):
        ok = p.evaluate("""()=>{const t=[...document.querySelectorAll('button,a,div')].reverse().find(e=>{const x=(e.innerText||'').trim();return x==='Setuju'||x==='SETUJU';});if(t){t.click();return true;}return false;}""")
        if ok:
            time.sleep(3); break
        time.sleep(1)
    time.sleep(2)
    return p.evaluate(JS_INTERSTITIAL)


def check_batch(phones, proxy=None, log=print):
    """Cek banyak nomor → dict {phone: {fresh, registered, channels, dom}}.
    Dipakai oleh bot (import). Buka 1 browser, loop nomor."""
    import fpgen
    out = {}
    px = proxy or PROXY
    HOST = px.split("@")[-1]; USER = px.split("//")[1].split(":")[0]
    PASS = px.split("//")[1].split("@")[0].split(":", 1)[1]
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage", "--use-gl=swiftshader"])
        c = b.new_context(user_agent=UA, locale="id-ID",
                          proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                          ignore_https_errors=False)
        p = c.new_page()
        p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        try:
            p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=2000, force=True); time.sleep(1.5)
        except Exception:
            pass
        for ph in phones:
            FP = fpgen.fp_shopee_ccd(ph)
            try:
                p.evaluate("(v)=>{try{document.cookie='shopee_webUnique_ccd='+v+'; path=/; domain=.shopee.co.id';}catch(e){}}", FP)
                r = p.evaluate(JS_CHECK, {"phone": ph, "fp": FP})
                j = (r or {}).get("json") or {}
                data = j.get("data") or {}
                ch = data.get("available_channels") or []
                dom = {}
                try:
                    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
                    time.sleep(2.0)
                    dom = dom_check(p, ph, FP)
                except Exception as e:
                    dom = {"err": str(e)[:60]}
                reg = dom.get("registered")
                fresh = (reg is False) if reg is not None else None
                out[ph] = {"fresh": fresh, "registered": reg, "channels": ch,
                           "error": j.get("error"), "dom": dom.get("text")}
                log(f"{ph} fresh={fresh} reg={reg} ch={ch} err={j.get('error')}")
            except Exception as e:
                out[ph] = {"err": str(e)[:80]}
            time.sleep(0.6)
        b.close()
    return out


if __name__ == "__main__":
    import fpgen
    phones = collect_phones()
    if not phones:
        print("usage: phone_checker.py <phone>|<a,b,c>|<file.txt>"); sys.exit(1)
    out = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage", "--use-gl=swiftshader"])
        c = b.new_context(user_agent=UA, locale="id-ID",
                          proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                          ignore_https_errors=False)
        p = c.new_page()
        p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        try:
            p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=2000, force=True); time.sleep(1.5)
        except Exception: pass
        for ph in phones:
            FP = fpgen.fp_shopee_ccd(ph)
            p.evaluate("(v)=>{try{document.cookie='shopee_webUnique_ccd='+v+'; path=/; domain=.shopee.co.id';}catch(e){}}", FP)
            # 1) API check (channel info)
            try:
                r = p.evaluate(JS_CHECK, {"phone": ph, "fp": FP})
            except Exception as e:
                out[ph] = {"err": str(e)[:80]}; print(f"{ph} ERR {str(e)[:60]}"); continue
            j = (r or {}).get("json") or {}
            data = j.get("data") or {}
            ch = data.get("available_channels") or []
            pref = data.get("preferred_channel")
            needcap = data.get("need_captcha")
            # 2) DOM check (interstitial = terdaftar) — re-load halaman bersih dulu
            dom = {}
            try:
                p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
                time.sleep(2.5)
                dom = dom_check(p, ph, FP)
            except Exception as e:
                dom = {"err": str(e)[:60]}
            registered = dom.get("registered")
            fresh = (registered is False) if registered is not None else None
            out[ph] = {"error": j.get("error"), "fresh": fresh, "registered": registered,
                       "channels": ch, "preferred": pref, "need_captcha": needcap,
                       "dom": dom.get("text")}
            if fresh is True:
                tag = "✅ FRESH (captcha muncul)"
            elif fresh is False:
                tag = "⛔ TERDAFTAR (interstitial)"
            else:
                tag = "❓ TAK PASTI"
            print(f"{ph}  {tag}  channels={ch} pref={pref} err={j.get('error')} dom={dom.get('text')}", flush=True)
            time.sleep(0.8)
        b.close()
    try:
        old = json.load(open(f"{ROOT}/phone_check.json"))
    except Exception:
        old = {}
    old.update(out)
    json.dump(old, open(f"{ROOT}/phone_check.json", "w"), indent=1)
    fresh_n = sum(1 for v in out.values() if v.get("fresh"))
    print(f"\n[checker] total={len(out)} fresh={fresh_n} terdaftar={len(out)-fresh_n} → phone_check.json")
