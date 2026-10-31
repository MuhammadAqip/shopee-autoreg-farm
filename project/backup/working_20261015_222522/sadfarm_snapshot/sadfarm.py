#!/usr/bin/env python3
"""sadfarm — SadCaptcha account farm + API key harvester.

Flow (per akun):
  1. generate email @mail.withu.my.id (catch-all, no setup)
  2. GET /register (ambil session + cookies)
  3. solve reCAPTCHA v2 (provider: 2captcha/capsolver/manual)
  4. POST /register
  5. poll inbox mail.withu.my.id → ambil activation link
  6. GET activation link (klik verify)
  7. POST /login
  8. GET /dashboard → scrape API key
  9. GET /api/v1/license/credits → konfirmasi 25 credits
  10. simpan hasil

Usage:
  sadfarm.py --count 5 --solver 2captcha --solver-key XXX
  sadfarm.py --count 1 --solver manual
"""
import os, sys, re, json, time, random, string, argparse, urllib.parse
import requests

MAIL_API = "https://mail.withu.my.id/api"
DOMAIN = "mail.withu.my.id"
SAD = "https://www.sadcaptcha.com"
RECAP_SITEKEY = "6LdRfgQqAAAAAMmRfNPmuSunXUrrYxnrJLEhPrdV"
RECAP_URL = f"{SAD}/register"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
ROOT = "/root/sadfarm"
OUT = f"{ROOT}/accounts.json"


def rand_user(n=10):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def rand_pass(n=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=n)) + "!1"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


# ---------- captcha solvers ----------

def solve_2captcha(key, sitekey, url):
    r = requests.get("http://2captcha.com/in.php", params={
        "key": key, "method": "userrecaptcha", "googlekey": sitekey,
        "pageurl": url, "json": 1}, timeout=30).json()
    if r.get("status") != 1:
        raise RuntimeError(f"2captcha submit: {r}")
    cid = r["request"]
    for _ in range(40):
        time.sleep(5)
        g = requests.get("http://2captcha.com/res.php", params={
            "key": key, "action": "get", "id": cid, "json": 1}, timeout=30).json()
        if g.get("status") == 1:
            return g["request"]
        if g.get("request") != "CAPCHA_NOT_READY":
            raise RuntimeError(f"2captcha: {g}")
    raise RuntimeError("2captcha timeout")


def solve_capsolver(key, sitekey, url):
    c = requests.post("https://api.capsolver.com/createTask", json={
        "clientKey": key,
        "task": {"type": "ReCaptchaV2TaskProxyLess", "websiteURL": url, "websiteKey": sitekey},
    }, timeout=30).json()
    tid = c.get("taskId")
    if not tid:
        raise RuntimeError(f"capsolver: {c}")
    for _ in range(40):
        time.sleep(5)
        g = requests.post("https://api.capsolver.com/getTaskResult", json={
            "clientKey": key, "taskId": tid}, timeout=30).json()
        if g.get("status") == "ready":
            return g["solution"]["gRecaptchaResponse"]
        if g.get("status") == "failed":
            raise RuntimeError(f"capsolver: {g}")
    raise RuntimeError("capsolver timeout")


def solve_manual(sitekey, url):
    print("\n=== MANUAL SOLVE ===")
    print(f"Buka: {url}")
    print(f"Solve reCAPTCHA, ambil token dari g-recaptcha-response")
    print("(DevTools → Network → cari 'recaptcha' → response token,")
    print(" atau console: grecaptcha.getResponse())")
    return input("Paste token: ").strip()


IMPORTANT_NOTES = """CAPSOLVER_OK"""


# ---------- mail helpers ----------

def mail_inbox(addr):
    try:
        r = requests.get(f"{MAIL_API}/mailbox/{addr}", timeout=20)
        return r.json().get("emails", [])
    except Exception:
        return []


def wait_activation(addr, timeout=120):
    """poll inbox cari link activation sadcaptcha."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        for e in mail_inbox(addr):
            body = (e.get("text", "") or "") + (e.get("html", "") or "")
            for m in re.finditer(r"https://www\.sadcaptcha\.com/activate/[^\s\"'<>\]]+", body):
                link = m.group(0).rstrip("]).,;").replace("&amp;", "&")
                if len(link) > 60:
                    return link
        time.sleep(5)
    return None


# ---------- sadcaptcha flow ----------

def register_one(email, password, solver, solver_key, proxy=None):
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}

    # 1. GET register (ambil cookies)
    s.get(f"{SAD}/register", timeout=20)

    # 2. solve captcha
    log(f"[{email}] solving reCAPTCHA via {solver}...")
    if solver == "2captcha":
        token = solve_2captcha(solver_key, RECAP_SITEKEY, RECAP_URL)
    elif solver == "capsolver":
        token = solve_capsolver(solver_key, RECAP_SITEKEY, RECAP_URL)
    else:
        token = solve_manual(RECAP_SITEKEY, RECAP_URL)
    log(f"[{email}] captcha token: {token[:30]}...")

    # 3. POST register
    r = s.post(f"{SAD}/register", data={
        "username": email, "password1": password, "password2": password,
        "agreeToTerms": "on", "g-recaptcha-response": token,
    }, allow_redirects=False, timeout=30)
    loc = r.headers.get("Location", "")
    log(f"[{email}] register -> {r.status_code} {loc}")
    # 302 ke /register = gagal; ke /login atau /dashboard = sukses
    if loc.rstrip("/").endswith("/register") or r.status_code != 302:
        return {"ok": False, "stage": "register", "email": email, "code": r.status_code, "loc": loc}

    # 4. tunggu activation email + klik
    log(f"[{email}] nunggu email verifikasi...")
    link = wait_activation(email, timeout=180)
    if not link:
        return {"ok": False, "stage": "verify_mail", "email": email}
    log(f"[{email}] activate: {link[:70]}...")
    av = s.get(link, allow_redirects=True, timeout=30)
    log(f"[{email}] activate -> {av.status_code}")

    # 5. login
    rl = s.post(f"{SAD}/login", data={"username": email, "password": password},
                allow_redirects=False, timeout=30)
    log(f"[{email}] login -> {rl.status_code} {rl.headers.get('Location','')}")
    if rl.status_code != 302 or "login" in rl.headers.get("Location", ""):
        return {"ok": False, "stage": "login", "email": email}

    # 6. dashboard → scrape apikey
    dh = s.get(f"{SAD}/dashboard", timeout=30).text
    keys = re.findall(r"[a-f0-9]{32}", dh)
    apikey = keys[0] if keys else ""
    if not apikey:
        return {"ok": False, "stage": "apikey", "email": email}

    # 7. cek credits
    credits = None
    try:
        cr = requests.get(f"{SAD}/api/v1/license/credits",
                          params={"licenseKey": apikey}, timeout=15).json()
        credits = cr.get("credits")
    except Exception:
        pass

    log(f"[{email}] ✅ API KEY={apikey} credits={credits}")
    return {"ok": True, "email": email, "password": password,
            "apikey": apikey, "credits": credits,
            "created": time.strftime("%Y-%m-%d %H:%M:%S")}


def load_accounts():
    if os.path.exists(OUT):
        try:
            return json.load(open(OUT))
        except Exception:
            return []
    return []


def save_account(acc):
    accs = load_accounts()
    accs.append(acc)
    json.dump(accs, open(OUT, "w"), indent=1, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--solver", default="2captcha", choices=["2captcha", "capsolver", "manual"])
    ap.add_argument("--solver-key", default=os.environ.get("SOLVER_KEY", ""))
    ap.add_argument("--password", default="")
    ap.add_argument("--proxy", default="")
    ap.add_argument("--start-from", default="")
    args = ap.parse_args()

    if args.solver in ("2captcha", "capsolver") and not args.solver_key:
        print("ERROR: --solver-key wajib buat 2captcha/capsolver"); sys.exit(1)

    ok_count = 0
    for i in range(args.count):
        email = (args.start_from if (i == 0 and args.start_from) else rand_user()) + "@" + DOMAIN
        pw = args.password or rand_pass()
        log(f"=== [{i+1}/{args.count}] {email} ===")
        try:
            res = register_one(email, pw, args.solver, args.solver_key, args.proxy or None)
        except Exception as e:
            res = {"ok": False, "stage": "exception", "email": email, "err": str(e)[:200]}
        if res.get("ok"):
            save_account(res)
            ok_count += 1
            log(f"SAVED → {res['apikey']} ({res['credits']} cr)")
        else:
            log(f"FAIL: {res}")
        if i < args.count - 1:
            time.sleep(random.randint(8, 20))

    log(f"=== DONE: {ok_count}/{args.count} sukses ===")
    print(json.dumps(load_accounts()[-ok_count:] if ok_count else [], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

