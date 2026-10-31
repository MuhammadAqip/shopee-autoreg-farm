#!/usr/bin/env python3
"""proxy_health.py — #7: cek kesehatan + geo semua proxy ID. Auto-pick terbaik.

Test tiap proxy: latency + geo (harus ID) via ip-api.com. Skor = ok + latency rendah.
Output: proxi_health.json (sorted terbaik dulu) + proxies_best.txt.
Dipakai bot utk auto-pick + rotate.

Usage: proxy_health.py [--list proxies_id_vs.txt] [--top 3]
"""
import sys, os, json, time, concurrent.futures as CF
import requests

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
LIST = f"{ROOT}/proxies_id_vs.txt"
TOP = 3
for a in sys.argv:
    if a.startswith("--list="): LIST = a.split("=", 1)[1]
    if a.startswith("--top="): TOP = int(a.split("=", 1)[1])
OUT = f"{ROOT}/proxy_health.json"

TEST_URL = "http://ip-api.com/json/?fields=status,countryCode,query,country"


def test_proxy(px):
    px = px.strip()
    if not px:
        return None
    if not px.startswith("http"):
        px = "http://" + px
    t0 = time.time()
    try:
        r = requests.get(TEST_URL, proxies={"http": px, "https": px}, timeout=15)
        dt = int((time.time() - t0) * 1000)
        j = r.json()
        cc = j.get("countryCode")
        ok = (j.get("status") == "success")
        return {"proxy": px, "ok": ok, "cc": cc, "ip": j.get("query"),
                "latency_ms": dt, "id_ok": cc == "ID",
                "score": (1000 if cc == "ID" else 0) + (500 if ok else 0) - min(dt, 4000)}
    except Exception as e:
        return {"proxy": px, "ok": False, "err": str(e)[:60], "score": -9999}


if __name__ == "__main__":
    try:
        plist = [l.strip() for l in open(LIST) if l.strip()]
    except Exception:
        plist = []
    print(f"[proxy_health] test {len(plist)} proxy...")
    res = []
    with CF.ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(test_proxy, plist):
            if r:
                res.append(r)
                flag = "✅ID" if r.get("id_ok") else ("🌍" + str(r.get("cc")) if r.get("ok") else "❌")
                print(f"  {flag} {r['proxy'].split('@')[-1]:22} {r.get('latency_ms','?')}ms  score={r['score']}")
    res.sort(key=lambda x: x["score"], reverse=True)
    json.dump(res, open(OUT, "w"), indent=1)
    best = [r["proxy"] for r in res if r.get("id_ok")][:TOP] or [r["proxy"] for r in res if r.get("ok")][:TOP]
    with open(f"{ROOT}/proxies_best.txt", "w") as f:
        for b in best:
            f.write(b + "\n")
    print(f"[proxy_health] ID-ok={sum(1 for r in res if r.get('id_ok'))}/{len(res)} → proxies_best.txt (top {len(best)})")
