#!/usr/bin/env python3
"""test_edge_solve.py — drag pakai jarak dari local_solver (edge-detect), cek verify PASS.
Kalau PASS → WA dialog muncul / send_vcode auto.
"""
import sys, time, json, random
from playwright.sync_api import sync_playwright
import local_solver as LS

PHONE = sys.argv[1] if len(sys.argv) > 1 else "6285849159568"
PROXY = open("/root/shopee-farm/proxies_id_vs.txt").readline().strip()
HOST = PROXY.split("@")[-1]; USER = PROXY.split("//")[1].split(":")[0]
PASS = PROXY.split("//")[1].split("@")[0].split(":", 1)[1]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
LOG = open("/root/shopee-farm/capture/captcha_wa_flow.jsonl", "a")
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
            try: e["r"]=(r.text() or "")[:1500]
            except: e["r"]=""
            rec(e)
            if any(k in e["u"] for k in ("verify_v2","send_vcode")): print(f'[CAP] {e["s"]} {e["u"].split("/")[-1]} RES={e["r"][:120]}',flush=True)
    p.on("request",on_req); p.on("response",on_resp)

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
    for i in range(45):
        time.sleep(1.5)
        cs=p.evaluate("()=>[...document.querySelectorAll('canvas')].map(c=>({w:c.width,h:c.height,d:c.getAttribute('draggable')}))")
        if cs: break
    for w in range(12):
        if "Memuat" not in p.evaluate("()=>document.body.innerText||''"): break
        time.sleep(1.5)
    # ambil puzzle+piece → local solve
    info=p.evaluate("""()=>{const pz=document.querySelector("aside canvas[draggable=false], #NEW_CAPTCHA canvas[draggable=false]");
      const pc=document.querySelector("aside canvas[draggable=true], #NEW_CAPTCHA canvas[draggable=true]");
      const o={};if(pz){const r=pz.getBoundingClientRect();o.puzzle=pz.toDataURL('image/png').split(',')[1];o.pw=r.width;}
      if(pc){const r=pc.getBoundingClientRect();o.piece=pc.toDataURL('image/png').split(',')[1];o.px=r.x;o.py=r.y;o.pcw=r.width;}
      // grip
      const all=[...document.querySelectorAll('*')];let g=null,bs=1e9;
      if(pz){const pb=pz.getBoundingClientRect().bottom;
        for(const e of all){const r=e.getBoundingClientRect();
          if(r.width>=34&&r.width<=60&&r.height>=34&&r.height<=60&&r.top>pb){if(r.x<bs){bs=r.x;g={x:r.x+r.width/2,y:r.y+r.height/2};}}}}
      o.grip=g;return o;}""")
    tgt,dbg=LS.solve_local(info["puzzle"], info["piece"], info["pw"])
    print("[local] target:",tgt,"dbg:",json.dumps({k:dbg.get(k) for k in ('src','tmpl_x','tmpl_score','gap_x_bitmap')}),flush=True)
    g=info["grip"]; sx,sy=g["x"],g["y"]
    # drag sampai target
    p.mouse.move(sx,sy); p.mouse.down(); time.sleep(0.15)
    steps=60
    for i in range(1,steps+1):
        p.mouse.move(sx+tgt*i/steps, sy+random.uniform(-1,1)); time.sleep(0.012)
    p.mouse.move(sx+tgt+2, sy); p.mouse.move(sx+tgt, sy); time.sleep(0.2); p.mouse.up()
    print(f"[drag] {tgt}px dari ({sx:.0f},{sy:.0f})",flush=True)
    time.sleep(6)
    body=p.evaluate("()=>document.body.innerText||''")
    print("[PAGE]", body[:250].replace("\n"," | "),flush=True)
    p.screenshot(path="/root/shopee-farm/shots/edge_solve.png",full_page=True)
    print("[done]",flush=True)
    time.sleep(2); c.close(); b.close()
