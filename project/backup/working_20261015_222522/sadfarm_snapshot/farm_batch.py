#!/usr/bin/env python3
"""farm_batch.py — batch farm SadCaptcha akun, auto-loop + proxy rotate + retry.

Usage:
  farm_batch.py --count 5
  farm_batch.py --count 10 --proxy-rotate --retry 2
  farm_batch.py --count 3 --callback /path/status.json  # live status file

Env:
  PROXY_LIST (optional path), default /root/shopee-farm/proxies_id_vs.txt
"""
import sys, os, time, json, random, argparse, re, subprocess

sys.path.insert(0, "/root/sadfarm")
import sadfarm as S

STATUS_FILE = "/root/sadfarm/farm_status.json"
PROXY_FILE = "/root/shopee-farm/proxies_id_vs.txt"
PY = "/root/sniffenv/bin/python"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_proxies():
    try:
        return [l.strip() for l in open(PROXY_FILE) if l.strip()]
    except Exception:
        return []


def write_status(st):
    try:
        json.dump(st, open(STATUS_FILE, "w"), indent=1, ensure_ascii=False)
    except Exception:
        pass


def run_one(proxy, log_f):
    """jalanin reg_solver.py untuk 1 akun (subprocess, headless via xvfb)."""
    email = S.rand_user() + "@" + S.DOMAIN
    pw = "Bantul2008#"
    cmd = ["xvfb-run", "-a", "--server-args=-screen 0 1280x900x24",
           PY, "/root/sadfarm/reg_solver.py", email, pw, "--headful"]
    if proxy:
        cmd += ["--proxy", proxy]
    with open(log_f, "w") as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=600)
    # cek hasil
    try:
        txt = open(log_f).read()
    except Exception:
        txt = ""
    m = re.search(r"apikey=([a-f0-9]{32}) credits=(\S+)", txt)
    if m:
        return {"ok": True, "email": email, "apikey": m.group(1),
                "credits": int(m.group(2)) if m.group(2).isdigit() else None}
    return {"ok": False, "email": email, "log": log_f}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--retry", type=int, default=1)
    ap.add_argument("--no-proxy", action="store_true")
    args = ap.parse_args()

    proxies = [] if args.no_proxy else load_proxies()
    st = {"running": True, "target": args.count, "done": 0, "ok": 0, "fail": 0,
          "results": [], "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    write_status(st)

    for i in range(args.count):
        ok = False
        for attempt in range(args.retry + 1):
            proxy = random.choice(proxies) if proxies else ""
            log(f"[{i+1}/{args.count}] attempt {attempt+1} proxy={proxy.split('@')[-1] if proxy else 'none'}")
            lf = f"/tmp/farm_{i}_{attempt}.log"
            try:
                res = run_one(proxy, lf)
            except subprocess.TimeoutExpired:
                res = {"ok": False, "email": "?", "log": lf, "err": "timeout"}
            if res.get("ok"):
                S.save_account({"ok": True, "email": res["email"], "password": "[REDACTED]",
                                "apikey": res["apikey"], "credits": res["credits"],
                                "created": time.strftime("%Y-%m-%d %H:%M:%S")})
                st["ok"] += 1
                st["results"].append({"email": res["email"], "apikey": res["apikey"], "credits": res["credits"]})
                log(f"  ✅ {res['apikey']} ({res['credits']} cr)")
                ok = True
                break
            else:
                log(f"  ❌ gagal ({res.get('log','')})")
        if not ok:
            st["fail"] += 1
            st["results"].append({"email": "?", "ok": False})
        st["done"] = i + 1
        write_status(st)
        if i < args.count - 1:
            time.sleep(random.randint(5, 15))

    st["running"] = False
    st["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    write_status(st)
    log(f"=== DONE: {st['ok']}/{args.count} sukses ===")
    print(json.dumps(st, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
