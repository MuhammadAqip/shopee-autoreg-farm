#!/usr/bin/env python3
"""wa_multi.py — (1)+(2)+(3) integrated: buka signup → captcha → MULTI-CANDIDATE drag
(edge/tmpl/dev) sampai verify PASS → deteksi dialog WA / send_vcode → klik Kirim ke WhatsApp.
Semua request di-capture ke capture/captcha_wa_flow.jsonl.

Usage: wa_multi.py <PHONE> [max_rounds]
"""
import sys, time, json, random
from playwright.sync_api import sync_playwright
import local_solver as LS

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6285849159568"
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 3   # jumlah puzzle di-retry
PROXY = open("/root/shopee-farm/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
LOG = open("/root/shopee-farm/capture/captcha_wa_flow.jsonl", "a")
STATE = {"last_verify": None, "send_fired": False}
def rec(d): LOG.write(json.dumps(d, ensure_ascii=False)+"\n"); LOG.flush()

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
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
            try: e["r"]=(r.text() or "")[:2000]
            except: e["r"]=""
            rec(e)
            if "verify_v2" in e["u"]: STATE["last_verify"]=e["r"]
            if "send_vcode" in e["u"]:
                STATE["send_fired"]=True
                print(f"[CAP] send_vcode {e['s']} RES={e['r'][:160]}", flush=True)
            if "generate" in e["u"]: print(f"[CAP] generate {e['s']}", flush=True)
    p.on("request",on_req); p.on("response",on_resp)

    def open_captcha():
        p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=60000)
        p.wait_for_selector("input[name='phone']", timeout=45000); time.sleep(4)
        try:
            mb=p.locator("button.shopee-button-outline").first
            if mb.count() and mb.is_visible(): mb.click(timeout=2500,force=True); time.sleep(3)
        except: pass
        inp=p.locator("input[name='phone']").first; inp.click(timeout=5000); inp.type(PHONE,delay=45); time.sleep(4)
        for lbl in ("BERIKUTNYA","Berikutnya"):
            try: p.locator(f"button:has-text('{lbl}')").first.click(timeout=3000,force=True); break
            except: pass
        time.sleep(3)
        for i in range(8):
            ok=p.evaluate("""()=>{const t=[...document.querySelectorAll('button,a,div')].reverse().find(e=>{const x=(e.innerText||'').trim();return x==='Setuju'||x==='SETUJU';});if(t){t.click();return true;}return false;}""")
            if ok: time.sleep(3); break
            time.sleep(2)
        for i in range(50):
            time.sleep(1.5)
            cs=p.evaluate("()=>[...document.querySelectorAll('canvas')].map(c=>({w:c.width,h:c.height,d:c.getAttribute('draggable')}))")
            if cs: break
        for w in range(14):
            if "Memuat" not in p.evaluate("()=>document.body.innerText||''"): break
            time.sleep(1.5)

    def grab():
        return p.evaluate("""()=>{const pz=document.querySelector("aside canvas[draggable=false], #NEW_CAPTCHA canvas[draggable=false]");
          const pc=document.querySelector("aside canvas[draggable=true], #NEW_CAPTCHA canvas[draggable=true]");
          const o={};if(pz){const r=pz.getBoundingClientRect();o.puzzle=pz.toDataURL('image/png').split(',')[1];o.pw=r.width;o.px=r.x;}
          if(pc){o.piece=pc.toDataURL('image/png').split(',')[1];}
          const all=[...document.querySelectorAll('*')];let g=null,bs=1e9;
          if(pz){const pb=pz.getBoundingClientRect().bottom;
            for(const e of all){const r=e.getBoundingClientRect();
              if(r.width>=34&&r.width<=60&&r.height>=34&&r.height<=60&&r.top>pb){if(r.x<bs){bs=r.x;g={x:r.x+r.width/2,y:r.y+r.height/2};}}}}
          o.grip=g; o.has_wa=(document.body.innerText||'').includes('WhatsApp');
          o.txt=(document.body.innerText||'').slice(0,200);return o;}""")

    def drag(sx, sy, dist):
        p.mouse.move(sx, sy); p.mouse.down(); time.sleep(0.15)
        steps=55
        for i in range(1, steps+1):
            p.mouse.move(sx+dist*i/steps, sy+random.uniform(-1,1)); time.sleep(0.012)
        p.mouse.move(sx+dist+2, sy); p.mouse.move(sx+dist, sy); time.sleep(0.2); p.mouse.up()

    open_captcha()
    solved = False
    for rnd in range(ROUNDS * 3):   # cukup banyak kesempatan
        info = grab()
        # cek dialog WA (tombol spesifik, bukan footer)
        wa_btn = p.evaluate("""()=>{const t=[...document.querySelectorAll('button,div,a')].find(e=>{const x=(e.innerText||'').trim();return x==='Kirim ke WhatsApp'||x.includes('Kirim ke WhatsApp')||x==='Kirim WhatsApp';});return !!t;}""")
        if wa_btn:
            print("[✓] dialog 'Kirim ke WhatsApp' muncul!", flush=True); solved = True; break
        if not info.get("puzzle") or not info.get("grip"):
            print(f"[round {rnd}] captcha hilang → cek halaman", flush=True); solved = True; break
        xs, dbg = LS.candidates(info["puzzle"], info["piece"], topk=3)
        print(f"[round {rnd}] kandidat: {xs} ({[c['src'] for c in dbg['candidates']]})", flush=True)
        vbefore = STATE["last_verify"]
        tried_all_fail = True
        for ci, x in enumerate(xs):
            dist = int(round(x * (info["pw"]/280.0)))
            drag(info["grip"]["x"], info["grip"]["y"], dist)
            print(f"   drag cand{ci} x={x} dist={dist}", flush=True)
            time.sleep(2.5)
            nw = p.evaluate("""()=>({wa:!![...document.querySelectorAll('button,div,a')].find(e=>{const x=(e.innerText||'').trim();return x==='Kirim ke WhatsApp'||x.includes('Kirim ke WhatsApp');}),
              has_canvas: !!document.querySelector("aside canvas[draggable=true], #NEW_CAPTCHA canvas[draggable=true]")})""")
            if nw.get("wa"): print("[✓] WA dialog!", flush=True); solved = True; break
            if not nw.get("has_canvas"): print("[✓] captcha hilang (PASS?)", flush=True); solved = True; break
            # verify berubah = puzzle baru; kandidat lama tidak valid → break ke re-grab
            if STATE["last_verify"] != vbefore:
                vbefore = STATE["last_verify"]
                # re-grab puzzle baru & solve ulang sekarang juga
                ni = grab()
                if ni.get("puzzle"):
                    nxs, ndbg = LS.candidates(ni["puzzle"], ni["piece"], topk=3)
                    print(f"      puzzle berganti → kandidat baru: {nxs}", flush=True)
                    # coba 1 kandidat teratas puzzle baru
                    if nxs:
                        nd = int(round(nxs[0] * (ni["pw"]/280.0)))
                        drag(ni["grip"]["x"], ni["grip"]["y"], nd)
                        print(f"      drag x={nxs[0]} dist={nd}", flush=True); time.sleep(3)
                        chk = p.evaluate("""()=>({wa:!![...document.querySelectorAll('button,div,a')].find(e=>{const x=(e.innerText||'').trim();return x.includes('Kirim ke WhatsApp');}),has:!!document.querySelector("aside canvas[draggable=true]")})""")
                        if chk.get("wa") or not chk.get("has"): solved = True; break
                break
        if solved: break
        if STATE["send_fired"]: solved = True; break
        time.sleep(1)

    time.sleep(3)
    body = p.evaluate("()=>document.body.innerText||''")
    print("[PAGE]", body[:300].replace("\n"," | "), flush=True)
    try:
        ok = p.evaluate("""()=>{const t=[...document.querySelectorAll('button,div,a')].find(e=>{const x=(e.innerText||'').trim();return x==='Kirim ke WhatsApp'||x.includes('Kirim ke WhatsApp');});if(t){t.click();return true;}return false;}""")
        if ok: print("[✓] klik 'Kirim ke WhatsApp'", flush=True); time.sleep(8)
    except: pass
    body2 = p.evaluate("()=>document.body.innerText||''")
    print("[FINAL]", body2[:300].replace("\n"," | "), flush=True)
    p.screenshot(path="/root/shopee-farm/shots/wa_multi.png", full_page=True)
    json.dump({"phone":PHONE,"send_fired":STATE["send_fired"],
               "cookies":{ck["name"]:ck["value"] for ck in c.cookies()}},
              open("/root/shopee-farm/captcha_wa_state.json","w"))
    print("[SAVED] send_fired =", STATE["send_fired"], flush=True)
    time.sleep(3); c.close(); b.close()
