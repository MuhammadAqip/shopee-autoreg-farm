#!/usr/bin/env python3
"""account_login_repair.py — Fix error=19: login ulang pakai user/password → ambil cookie penuh (SPC_U/SPC_ST).

Alur:
  1. Buka shopee.co.id/buyer/login (browser Playwright)
  2. Isi nomor + password → submit
  3. Kalau minta OTP → tandai LUH_PERLU_OTP (manual)
  4. Kalau sukses → tangkap cookie baru (SPC_U, SPC_ST) → update account_result.json

Usage:
  account_login_repair.py <phone> [--proxy=...] [--headless]
  account_login_repair.py --all [--limit N]
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
ACC = os.path.join(ROOT, "account_result.json")
UA_MOBILE = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def parse_proxy(proxy):
    import re
    if not proxy:
        return None
    s = proxy.strip()
    m = re.match(r"(\w+)://([\d.]+):(\d+)", s)
    if not m:
        return None
    scheme, host, port = m.groups()
    return {"server": f"{scheme}://{host}:{port}"}


def load_accounts():
    out = []
    for l in open(ACC):
        l = l.strip()
        if not l:
            continue
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out


def save_accounts(accs):
    with open(ACC, "w") as f:
        for a in accs:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")


def extract_cookie(ctx):
    return "; ".join(f"{c['name']}={c['value']}" for c in ctx.cookies())


def cookie_has_session(cookie_str):
    import re
    return bool(re.search(r"SPC_U=", cookie_str)) and bool(re.search(r"SPC_ST=", cookie_str))


def repair(phone, password, proxy=None, headless=True):
    from playwright.sync_api import sync_playwright
    pxy = parse_proxy(proxy)
    res = {"phone": phone, "ok": False, "stage": "", "msg": ""}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=headless, proxy=pxy,
                              args=["--no-sandbox", "--disable-dev-shm-usage",
                                    "--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=UA_MOBILE, viewport={"width": 412, "height": 915},
                            locale="id-ID")
        pg = ctx.new_page()
        try:
            log(f"{phone}: buka login page")
            pg.goto("https://shopee.co.id/buyer/login", wait_until="domcontentloaded", timeout=45000)
            # tunggu input nomor muncul (robust — kadang captcha page dulu)
            got = False
            for _ in range(40):
                try:
                    if pg.locator("input[type='text']").count() or pg.locator("input[placeholder*='Handphone']").count():
                        got = True
                        break
                except Exception:
                    pass
                time.sleep(1)
            if not got:
                res["msg"] = "input login tak muncul (captcha/blank)"
                res["stage"] = pg.url
                ck0 = extract_cookie(ctx)
                res["cookie"] = ck0
                return res
            time.sleep(1)
            # isi nomor
            for sel in ["input[placeholder*='Handphone']", "input[placeholder*='Email']",
                        "input[type='text']"]:
                try:
                    loc = pg.locator(sel).first
                    if loc.count():
                        loc.click(timeout=3000, force=True)
                        loc.fill(phone)
                        break
                except Exception:
                    continue
            time.sleep(1)
            # isi password
            for sel in ["input[placeholder='Password']", "input[type='password']"]:
                try:
                    loc = pg.locator(sel).first
                    if loc.count():
                        loc.click(timeout=3000, force=True)
                        loc.fill(password)
                        break
                except Exception:
                    continue
            time.sleep(1)
            # klik login — FORCE (bypass overlay) → fallback JS click
            clicked = False
            for sel in ["button:has-text('Log in')", "button:has-text('Log In')",
                        "button:has-text('Masuk')", "button[type='submit']"]:
                try:
                    loc = pg.locator(sel).first
                    if loc.count():
                        loc.click(timeout=5000, force=True)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                try:
                    pg.evaluate("()=>{const b=[...document.querySelectorAll('button')].find(x=>/log ?in|masuk/i.test(x.innerText));if(b)b.click();}")
                except Exception:
                    pass
            time.sleep(10)
            res["stage"] = pg.evaluate("()=>location.href")
            txt = pg.evaluate("()=>document.body.innerText||''").lower()
            # cek hasil
            ck = extract_cookie(ctx)
            if cookie_has_session(ck):
                res["ok"] = True
                res["msg"] = "LOGIN OK — session didapat"
                res["cookie"] = ck
                # ambil user id
                import re
                m = re.search(r"SPC_U=(\d+)", ck)
                if m:
                    res["user_id"] = m.group(1)
            elif "otp" in txt or "verifikasi" in txt or "kode" in txt:
                res["stage"] = "OTP_REQUIRED"
                res["msg"] = "butuh OTP (manual)"
                res["cookie"] = ck
            else:
                res["msg"] = f"gagal login — stage={res['stage'][:60]}"
                res["cookie"] = ck
        except Exception as e:
            res["msg"] = f"{type(e).__name__}: {str(e)[:80]}"
        finally:
            try:
                b.close()
            except Exception:
                pass
    return res


def main():
    args = sys.argv[1:]
    proxy = None
    headless = "--headless" in args
    for a in args:
        if a.startswith("--proxy="):
            proxy = a.split("=", 1)[1]
    phones = [a for a in args if not a.startswith("--")]

    accs = load_accounts()
    if not phones:
        # repair semua yg error=19
        targets = [a for a in accs if not a.get("validated") and not a.get("user_id")]
    else:
        targets = [a for a in accs if a.get("phone") in phones]
    log(f"target: {len(targets)} akun")

    fixed = 0
    for a in targets:
        ph = a.get("phone")
        pw = a.get("password") or "PASS_REDACTED"
        r = repair(ph, pw, proxy=proxy, headless=headless)
        log(f"{ph}: ok={r['ok']} | {r['msg']}")
        if r["ok"]:
            a["cookie"] = r["cookie"]
            a["validated"] = True
            a["validate_msg"] = "AKTIF (repaired)"
            if r.get("user_id"):
                a["user_id"] = r["user_id"]
            fixed += 1
            # validasi ulang
            try:
                import validate_account as VA
                v = VA.validate(r["cookie"])
                if v.get("ok"):
                    a["user_id"] = v.get("userid") or a.get("user_id")
                    log(f"  ✅ revalidate OK → user_id={a['user_id']}")
                else:
                    log(f"  ⚠️ cookie ada tapi revalidate: {v.get('reason')}")
            except Exception:
                pass
        elif r.get("stage") == "OTP_REQUIRED":
            a["validate_msg"] = "PERLU_OTP"
        save_accounts(accs)

    log(f"SELESAI: {fixed}/{len(targets)} dipulihkan")


if __name__ == "__main__":
    main()
