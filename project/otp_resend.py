#!/usr/bin/env python3
"""otp_resend.py — fitur RESEND OTP via API (maximal API, browser tipis).

Alur (dari dalam page context → signature sz-sdk otomatis valid):
  1. buka /buyer/signup (headless) + inject fingerprint
  2. get_settings_v2 {operation:8, phone} → cek available_channels, need_captcha
  3. kalau need_captcha: solve captcha kecil (resend gambar) → verify_v2 → security_data
  4. send_vcode {channel:3, operation:8, m_token:security_data}
  5. capture SEMUA ke capture/resend_<phone>_<ts>.jsonl

Mode:
  --in-page   (default) fetch dari dalam page → SDK sign valid
  --session   pakai cookies+fp dari capture terakhir (pure requests)

Usage: otp_resend.py <FULL_PHONE> [--channel 3] [--headless]
"""
import sys, os, time, json, hashlib
from playwright.sync_api import sync_playwright

ROOT = "/root/shopee-farm"
sys.path.insert(0, ROOT)
PHONE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "6285353984860"
CHANNEL = 3
HEADLESS = "--headless" in sys.argv
for a in sys.argv:
    if a.startswith("--channel="): CHANNEL = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
CAPF = f"{ROOT}/capture/resend_{PHONE}_{int(time.time())}.jsonl"
CAP = open(CAPF, "a")


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
    CAP.write(json.dumps({"t": time.time(), "log": m}) + "\n"); CAP.flush()


import fpgen  # noqa: E402
FP = fpgen.fp_shopee_ccd(PHONE)

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=HEADLESS, args=["--no-sandbox",
        "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server": "http://"+HOST, "username": USER, "password": PASS},
                      ignore_https_errors=False, viewport={"width": 1280, "height": 900})
    c.add_cookies([{"name": "shopee_webLanguage", "value": "id", "domain": ".shopee.co.id", "path": "/"},
                   {"name": "shopee_webUnique_ccd", "value": FP, "domain": ".shopee.co.id", "path": "/"}])
    p = c.new_page()
    p.add_init_script("try{document.cookie='shopee_webUnique_ccd=%s; path=/; domain=.shopee.co.id';}catch(e){}" % FP)
    # CDP capture
    cdp = c.new_cdp_session(p); cdp.send("Network.enable")
    _bd = {}
    def _rq(e):
        try:
            r = e.get("request", {}); u = r.get("url", "")
            if any(k in u for k in ("/api/", "captcha", "otp")):
                _bd[e["requestId"]] = {"url": u, "method": r.get("method"), "postData": r.get("postData", "")}
        except Exception: pass
    def _rs(e):
        try:
            rec = _bd.get(e["requestId"])
            if rec:
                rec["status"] = e.get("response", {}).get("status")
                CAP.write(json.dumps(rec) + "\n"); CAP.flush()
        except Exception: pass
    cdp.on("Network.requestWillBeSent", _rq); cdp.on("Network.responseReceived", _rs)

    log(f"buka signup + fingerprint inject; capture → {CAPF}")
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)
    # [ENH-CAP2] hook fetch/XHR in-page → tangkap security_data dari verify_v2 (tanpa mitm)
    p.evaluate("""()=>{
      window.__SEC__=null; window.__CAPV__=[];
      const of=window.fetch;
      window.fetch=async function(){
        const r=await of.apply(this,arguments);
        try{
          const u=(arguments[0]&&arguments[0].url)||String(arguments[0]);
          if(u.indexOf('captcha/verify')>=0){
            const c=r.clone();
            c.json().then(j=>{ if(j&&j.security_data){ window.__SEC__=j.security_data; window.__CAPV__.push({ok:true}); } }).catch(()=>{});
          }
        }catch(e){}
        return r;
      };
      const oo=XMLHttpRequest.prototype.open;
      const os=XMLHttpRequest.prototype.send;
      XMLHttpRequest.prototype.open=function(m,u){ this.__u=u; return oo.apply(this,arguments); };
      XMLHttpRequest.prototype.send=function(){
        const self=this;
        self.addEventListener('load',function(){
          try{
            if((self.__u||'').indexOf('captcha/verify')>=0){
              const j=JSON.parse(self.responseText);
              if(j&&j.security_data){ window.__SEC__=j.security_data; window.__CAPV__.push({ok:true}); }
            }
          }catch(e){}
        });
        return os.apply(this,arguments);
      };
    }""")
    log("[CAP] hook fetch/XHR security_data terpasang")
    try:
        p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=2000, force=True); time.sleep(2)
    except Exception: pass

    # get_settings_v2 dari dalam page (SDK sign)
    js = """async (args)=>{
      const post=async(u,b)=>{const r=await fetch(u,{method:'POST',credentials:'include',
        headers:{'Content-Type':'application/json','x-api-source':'pc','x-requested-with':'XMLHttpRequest',
        'af-ac-enc-dat':''},body:JSON.stringify(b)});let j=null;try{j=await r.json();}catch(e){j={pe:String(e)};}
        return {status:r.status,json:j};};
      const cks=document.cookie.split('; ').reduce((a,c)=>{const i=c.indexOf('=');a[c.slice(0,i)]=c.slice(i+1);return a;},{});
      const fp=cks['shopee_webUnique_ccd']||args.fp||'';
      const ci={security_device_fingerprint:fp};
      const r1=await post('/api/v4/otp/get_settings_v2',{operation:8,phone:args.phone,
        supported_channels:[1,2,3,6,0,5],support_session:true,client_identifier:ci});
      return {settings:r1, fp};
    }"""
    r = p.evaluate(js, {"phone": PHONE, "fp": FP})
    log(f"get_settings_v2 → {json.dumps(r.get('settings',{}))[:260]}")

    settings = (r.get("settings") or {}).get("json") or {}
    data = settings.get("data") or {}
    avail = data.get("available_channels"); need_cap = data.get("need_captcha")
    log(f"available_channels={avail} need_captcha={need_cap}")

    # kalau butuh captcha → solve via sadcaptcha (alur penuh spt shopee_hold)
    sec_token = ""
    if need_cap:
        log("need_captcha=True → solve captcha (get puzzle → sadcaptcha → verify_v2)")
        try:
            import time as _t
            # 1. isi nomor + klik BERIKUTNYA agar captcha muncul
            from tools.signup_driver import fill_field
            fill_field(p, 0, PHONE); _t.sleep(1.5)
            for sel in ["button:has-text('BERIKUTNYA')", "text=BERIKUTNYA", "button:has-text('Berikutnya')"]:
                try:
                    loc = p.locator(sel).first
                    if loc.count():
                        bb = loc.bounding_box()
                        if bb:
                            p.mouse.move(bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2); _t.sleep(0.15)
                            p.mouse.down(); _t.sleep(0.08); p.mouse.up(); break
                except Exception: pass
            _t.sleep(3)
            # setuju TOS
            for _ in range(8):
                ok = p.evaluate("""()=>{const t=[...document.querySelectorAll('button,a,div')].reverse().find(e=>{const x=(e.innerText||'').trim();return x==='Setuju'||x==='SETUJU';});if(t){t.click();return true;}return false;}""")
                if ok: _t.sleep(3); break
                _t.sleep(1.5)
            # tunggu captcha muncul
            for _ in range(50):
                _t.sleep(1.5)
                if p.evaluate("()=>!!document.querySelector('#NEW_CAPTCHA, #captchaMask, #puzzleImgComponent')"): break
            # panggil solver shopee_hold
            import shopee_hold as SH
            KEY = open(f"{ROOT}/bot_key.txt").read().strip()
            for _src in (["cache"], ["cache", "api"]):
                res = SH.solve_image_crawl(p, KEY)
                log(f"solve → {json.dumps(res)[:200]}")
                if res.get("ok"):
                    break
                _t.sleep(2)
            # setelah solve → verify_v2 sudah jalan; ambil security_data dari hook
            for _w in range(20):
                sec_token = p.evaluate("()=>window.__SEC__||''") or ""
                if sec_token: break
                _t.sleep(0.5)
            log(f"security_data={'ADA ('+str(len(sec_token))+' char)' if sec_token else 'kosong'}")
        except Exception as e:
            log(f"solver err {str(e)[:100]}")

    # send_vcode — coba channel yg diminta (3=wa) lalu fallback
    order = [CHANNEL] + [x for x in (3, 1, 2) if x != CHANNEL]
    for ch in order:
        js2 = """async (args)=>{
          const r=await fetch('/api/v4/otp/send_vcode',{method:'POST',credentials:'include',
            headers:{'Content-Type':'application/json','x-api-source':'pc','x-requested-with':'XMLHttpRequest'},
            body:JSON.stringify({channel:args.ch,operation:8,phone:args.phone,m_token:args.sec,
              supported_channels:[1,2,3,6,0,5],client_identifier:{security_device_fingerprint:args.fp}})});
          let j=null;try{j=await r.json();}catch(e){j={pe:String(e)};}
          return {status:r.status,json:j};}"""
        res = p.evaluate(js2, {"ch": ch, "phone": PHONE, "sec": sec_token, "fp": FP})
        log(f"send_vcode channel={ch} → {json.dumps(res)[:200]}")
        j = res.get("json") or {}
        if j.get("error") == 0:
            log(f"★ OTP TERKIRIM via channel={ch} (WA={ch==3})")
            break
    CAP.write(json.dumps({"FINAL": True, "phone": PHONE, "capture": CAPF}) + "\n")
    log(f"selesai. capture={CAPF}")
    time.sleep(2)
    b.close()
