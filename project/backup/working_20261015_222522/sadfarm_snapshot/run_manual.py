#!/usr/bin/env python3
"""run_manual.py — jalankan sadfarm 1 akun mode MANUAL (opsi C).

Lu solve reCAPTCHA di browser, paste token ke file .token_input,
gw lanjut otomatis (register→verify→login→harvest).

Usage:
  run_manual.py            # email auto
  run_manual.py <email>    # email spesifik
"""
import sys, os, time, json
sys.path.insert(0, "/root/sadfarm")
import sadfarm as S

TOKEN_FILE = "/root/sadfarm/.token_input"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def main():
    email = (sys.argv[1] if len(sys.argv) > 1 else S.rand_user()) + "@" + S.DOMAIN
    pw = S.rand_pass()
    try:
        os.remove(TOKEN_FILE)
    except Exception:
        pass

    log(f"EMAIL    : {email}")
    log(f"PASSWORD : {pw}")
    log(f"STEP 1: buka https://www.sadcaptcha.com/register")
    log(f"STEP 2: isi email+password di atas, solve reCAPTCHA")
    log(f"STEP 3: ambil token -> tulis ke {TOKEN_FILE}")
    log("  cara ambil token:")
    log("   a) Console: grecaptcha.getResponse()  (paste hasilnya)")
    log("   b) Network tab: filter 'recaptcha' → response body ada 'g-recaptcha-response'")
    log(f"STEP 4: tulis token ke file: echo 'TOKEN' > {TOKEN_FILE}")
    log("gw tungguin...")

    token = None
    t0 = time.time()
    while time.time() - t0 < 900:
        if os.path.exists(TOKEN_FILE):
            token = open(TOKEN_FILE).read().strip()
            if token and len(token) > 50:
                break
        time.sleep(3)

    if not token:
        log("token timeout"); return
    log(f"token diterima: {token[:40]}...")

    # lanjut register
    import requests, re
    s = requests.Session()
    s.headers.update({"User-Agent": S.UA})
    s.get(f"{S.SAD}/register", timeout=20)
    r = s.post(f"{S.SAD}/register", data={
        "username": email, "password1": pw, "password2": pw,
        "agreeToTerms": "on", "g-recaptcha-response": token,
    }, allow_redirects=False, timeout=30)
    loc = r.headers.get("Location", "")
    log(f"register -> {r.status_code} {loc}")
    if loc.rstrip("/").endswith("/register") or r.status_code != 302:
        log("REGISTER GAGAL (token invalid/expired?)"); return

    log("nunggu email verifikasi...")
    link = S.wait_activation(email, timeout=180)
    if not link:
        log("email verifikasi ga dateng"); return
    log(f"activate: {link[:70]}...")
    s.get(link, allow_redirects=True, timeout=30)

    rl = s.post(f"{S.SAD}/login", data={"username": email, "password": pw},
                allow_redirects=False, timeout=30)
    log(f"login -> {rl.status_code} {rl.headers.get('Location','')}")

    dh = s.get(f"{S.SAD}/dashboard", timeout=30).text
    keys = re.findall(r"[a-f0-9]{32}", dh)
    apikey = keys[0] if keys else ""
    credits = None
    if apikey:
        try:
            import requests as R2
            credits = R2.get(f"{S.SAD}/api/v1/license/credits",
                             params={"licenseKey": apikey}, timeout=15).json().get("credits")
        except Exception:
            pass

    if apikey:
        acc = {"ok": True, "email": email, "password": pw, "apikey": apikey,
               "credits": credits, "created": time.strftime("%Y-%m-%d %H:%M:%S")}
        S.save_account(acc)
        log(f"✅ SUCCESS! apikey={apikey} credits={credits}")
        print(json.dumps(acc, indent=1, ensure_ascii=False))
    else:
        log("gagal ambil apikey")


if __name__ == "__main__":
    main()
