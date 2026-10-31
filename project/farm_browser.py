"""Shopee auto-register FARM — browser-driven (Playwright), multi-akun.

Ini runner NYATA: browser menjalankan bundle `browser-signals` sehingga token
(`security_device_fingerprint`, `af-ac-enc-dat`) + captcha ditangani seperti
user asli. Lihat auto_reg.py untuk chain detail + SNIFF_A_RESULTS.md untuk bukti.

Alur per akun:
  1. browser fresh context (atau proxy per akun)
  2. chain UI signup  → get_settings_v2
  3. captcha: reCAPTCHA v2 (desktop) / slider (mobile) → solver
  4. send_otp → tunggu OTP (sink) → verify → akun dibuat
  5. store ke SQLite (resumable)

Usage:
  python3 farm_browser.py --count 5 --sink file --proxy-file proxies.txt
  python3 farm_browser.py --count 1 --dry-run
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.accounts import AccountGen
from core.store import Store
from tools.proxy import ProxyPool, ManualOTP, HTTPOTP
from tools import captcha as capmod

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("install playwright: pip install playwright && playwright install chromium")
    sys.exit(1)


SIGNUP = "https://shopee.co.id/buyer/signup"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


class BrowserFarm:
    def __init__(self, headless=True, otp_sink=None, solver=None, shot_dir="/root/shopee-farm/shots"):
        self.headless = headless
        self.otp = otp_sink or ManualOTP()
        self.solver = solver
        self.shot_dir = Path(shot_dir)
        self.shot_dir.mkdir(parents=True, exist_ok=True)

    # --- UI helpers (sama seperti auto_reg.py, disatukan) ---
    @staticmethod
    def _dismiss_lang(page):
        for sel in ["text=Bahasa Indonesia", "text=Oke", "text=English"]:
            try:
                page.click(sel, timeout=5000)
                time.sleep(1.5)
                return True
            except Exception:
                continue
        return False

    @staticmethod
    def _fill_phone(page, phone):
        loc = None
        for sel in ["input[type='tel']", "input[placeholder*='Telepon']",
                    "input[type='text']", "input:visible"]:
            try:
                c = page.locator(sel).first
                if c.count() and c.is_visible():
                    loc = c
                    break
            except Exception:
                continue
        loc.wait_for(state="visible", timeout=15000)
        loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        loc.type(phone[1:] if phone.startswith("0") else phone, delay=55)

    @staticmethod
    def _click(page, *sels):
        for sel in sels:
            try:
                page.click(sel, timeout=5000)
                return True
            except Exception:
                continue
        return False

    def register_one(self, profile, proxy=None):
        captured = {}
        result = {"phone": profile["phone"], "name": profile["name"], "steps": []}

        def on_response(r):
            u = r.url
            if "/api/v4/otp/get_settings_v2" in u:
                try:
                    captured["get_settings_v2"] = r.json()
                except Exception:
                    captured["get_settings_v2"] = {"status": r.status}
            elif "/api/v4/otp/send_otp" in u:
                try:
                    captured["send_otp"] = r.json()
                except Exception:
                    captured["send_otp"] = {"status": r.status}
            elif "/api/v4/account/verify" in u:
                try:
                    captured["verify"] = r.json()
                except Exception:
                    captured["verify"] = {"status": r.status}

        launch = {"headless": self.headless,
                  "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        if proxy:
            launch["proxy"] = {"server": proxy}

        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch)
            ctx = browser.new_context(user_agent=UA, locale="id-ID",
                                      viewport={"width": 412, "height": 915},
                                      is_mobile=True, has_touch=True)
            page = ctx.new_page()
            page.on("response", on_response)
            shot = lambda tag: page.screenshot(path=str(self.shot_dir / f"{profile['phone']}_{tag}.png"))
            try:
                page.goto(SIGNUP, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3)
                self._dismiss_lang(page)
                result["steps"].append("lang")

                self._fill_phone(page, profile["phone"])
                result["steps"].append("phone")
                time.sleep(1)
                self._click(page, "input[type='checkbox']", "[class*='checkbox']")
                self._click(page, "button:has-text('Berikutnya')", "text=Berikutnya")
                result["steps"].append("next")
                time.sleep(2)
                self._click(page, "button:has-text('Setuju')", "text=Setuju")
                result["steps"].append("tos")

                # tunggu get_settings_v2
                for _ in range(30):
                    if "get_settings_v2" in captured:
                        break
                    time.sleep(1)
                gs = captured.get("get_settings_v2") or {}
                result["get_settings_v2"] = gs
                need_cap = (gs.get("data") or {}).get("need_captcha")
                result["need_captcha"] = need_cap
                result["captcha_scene"] = (gs.get("data") or {}).get("captcha_scene")
                try:
                    shot("captcha")
                except Exception:
                    pass

                # ---- captcha solve (reCAPTCHA v2 desktop / slider mobile) ----
                if need_cap and self.solver:
                    scene = result["captcha_scene"]
                    if scene == "signup":
                        # coba deteksi sitekey reCAPTCHA di DOM
                        sitekey = None
                        try:
                            sitekey = page.get_attribute("iframe[src*='recaptcha']", "src")
                        except Exception:
                            pass
                        tok = self.solver.solve_recaptcha_v2(sitekey, SIGNUP) if sitekey else None
                        if tok:
                            page.evaluate("(t)=>{ "
                                          "const el=document.querySelector('#g-recaptcha-response');"
                                          "if(el){el.value=t; el.dispatchEvent(new Event('change'));}}", tok)
                            result["steps"].append("captcha_solved")
                            self._click(page, "button:has-text('Berikutnya')", "button:has-text('Daftar')")
                else:
                    result["steps"].append("captcha_manual_pending")

                # tunggu send_otp
                for _ in range(45):
                    if "send_otp" in captured:
                        break
                    time.sleep(1)
                result["send_otp"] = captured.get("send_otp")

                # OTP → verify
                otp = self.otp.wait(profile["phone"], timeout=180)
                result["otp"] = otp
                if otp:
                    self._click(page, "input[type='tel']:visible", "input:visible")
                    page.keyboard.type(otp, delay=90)
                    time.sleep(1)
                    self._click(page, "button:has-text('Berikutnya')", "button:has-text('Verifikasi')",
                                "button:has-text('Daftar')")
                    time.sleep(3)
                    result["steps"].append("otp_submitted")
                    result["verify"] = captured.get("verify")
            except Exception as e:
                result["error"] = f"{type(e).__name__}: {e}"
                try:
                    shot("error")
                except Exception:
                    pass
            finally:
                browser.close()
        return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--headless", default="true")
    ap.add_argument("--proxy-file")
    ap.add_argument("--workers", type=int, default=1, help="(serial untuk tabrakan) ")
    ap.add_argument("--db", default="/root/shopee-farm/accounts.db")
    args = ap.parse_args()

    gen = AccountGen()
    store = Store(args.db)
    pool = ProxyPool()
    if args.proxy_file and Path(args.proxy_file).exists():
        pool.load_file(args.proxy_file)

    solver = capmod.get_solver() if os.environ.get("CAP_API_KEY") else None
    farm = BrowserFarm(headless=(args.headless.lower() == "true"), solver=solver)

    made = 0
    for i in range(args.count):
        p = gen.profile()
        key = p["phone"]
        device = {"spc_id": p.get("username", ""), "ua": UA}
        store.insert(p, device, None)
        if args.dry_run:
            store.update(key, status="dry")
            print(f"[dry] {p['name']} | {p['phone']} | {p['password']}")
            made += 1
            continue
        proxy = pool.acquire(key)
        print(f"[{i+1}/{args.count}] {p['phone']} proxy={proxy}")
        res = farm.register_one(p, proxy=proxy)
        ok = bool(res.get("send_otp") and not res.get("send_otp", {}).get("error"))
        store.update(key, status="otp_sent" if ok else "failed",
                     error=res.get("error"), proxy=proxy)
        print(json.dumps({k: res.get(k) for k in ("steps", "need_captcha", "otp", "error")}, ensure_ascii=False))
        made += 1 if ok else 0

    print(f"\nselesai — {made}/{args.count} sukses. DB: {args.db}")


if __name__ == "__main__":
    main()
