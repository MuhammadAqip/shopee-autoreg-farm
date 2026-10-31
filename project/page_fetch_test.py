#!/usr/bin/env python3
"""page_fetch_test.py — TEST Option A: page-context fetch (SDK auto-sign).

Hipotesis: fetch dari dalam page → SDK (yang wrap window.fetch) auto-inject
x-sap-ri / x-sap-sec / af-ac-enc-dat / af-ac-enc-sz-token. Kita TIDAK set header manual.

Test: panggil endpoint ringan (get_active_login_page / get_footer_layout) dari page,
cek apakah header anti-fraud muncul otomatis.

Kalau ya → Option A TERBUKTI → produksi bisa pakai.
"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
SECONDS = 30
for a in sys.argv:
    if a.startswith("--seconds="): SECONDS = int(a.split("=", 1)[1])
PROXY = open(f"{ROOT}/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox","--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage","--use-gl=swiftshader"])
    c = b.new_context(user_agent=UA, locale="id-ID",
                      proxy={"server":"http://"+HOST,"username":USER,"password":PASS}, ignore_https_errors=False)
    p = c.new_page()
    # hook fetch buat rekam header outgoing
    p.add_init_script("""
      window.__REQ=[];
      const _f=window.fetch;
      window.fetch=function(){
        try{ const a=arguments; const opt=a[1]||{}; const h=opt.headers||{};
          let hd={}; if(h && typeof h.forEach==='function'){h.forEach((v,k)=>hd[k]=v);} else {hd=h;}
          const rec={url:(typeof a[0]==='string'?a[0]:(a[0]&&a[0].url)||''),method:opt.method||'GET',hdrs:hd,ts:Date.now()};
          window.__REQ.push(rec);
        }catch(e){}
        return _f.apply(this,arguments);
      };
    """)
    print("[test] load page...")
    p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
    time.sleep(6)
    try: p.locator("button:has-text('Bahasa Indonesia')").first.click(timeout=2000, force=True); time.sleep(2)
    except Exception: pass
    print(f"[test] tunggu {SECONDS}s biar SDK init..."); time.sleep(SECONDS)
    # SEKARANG test: panggil endpoint ringan dari PAGE (SDK harus auto-sign)
    print("[test] panggil endpoint dari page (SDK auto-sign?)...")
    res = p.evaluate("""async ()=>{
      const out={};
      async function call(url, method, body){
        try{
          const opt={method:method||'GET', credentials:'include',
                     headers:{'Content-Type':'application/json','x-api-source':'pc','x-requested-with':'XMLHttpRequest'}};
          if(body) opt.body=JSON.stringify(body);
          const r=await fetch(url,opt);
          let t=''; try{t=await r.text();}catch(e){t=String(e);}
          return {status:r.status, body:t.slice(0,300)};
        }catch(e){return {err:String(e).slice(0,150)};}
      }
      out.footer = await call('/api/v4/pages/get_footer_layout');
      out.loginpage = await call('/api/v2/authentication/get_active_login_page');
      out.reqs = window.__REQ.filter(r=>/get_footer|get_active_login|abtest/.test(r.url));
      return out;
    }""")
    b.close()

print(json.dumps({"footer":res.get("footer"),"loginpage":res.get("loginpage")}, indent=1)[:400])
print("\n=== outgoing requests captured ===")
for r in (res.get("reqs") or [])[:6]:
    print(f"  {r['method']} {r['url'][:55]}")
    for k,v in r['hdrs'].items():
        if 'sap' in k.lower() or 'af-ac' in k.lower() or 'sz-token' in k.lower() or 'csrf' in k.lower():
            print(f"      {k}: {str(v)[:70]}")
