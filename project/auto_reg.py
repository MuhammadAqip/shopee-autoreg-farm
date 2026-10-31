"""Auto-register Shopee ID — browser nyata (Playwright).

Alasan: `security_device_fingerprint` + `af-ac-enc-dat` di-generate oleh bundle
`browser-signals` di dalam halaman. Requests polos tidak bisa — header itu wajib
dan server menolak tanpa itu. Browser nyata menghasilkan semuanya otomatis.

Chain (terekam di SNIFF_A_RESULTS.md):
  GET /buyer/signup
    → gate bahasa "Oke"
    → isi input[type=tel]
    → cek TOS → klik "Berikutnya"
    → modal "Simak Ketentuan Akun Shopee" → "Setuju"
    → POST /api/v4/otp/get_settings_v2  (need_captcha:true)
    → slider captcha (solver/manual)
    → POST /api/v4/otp/send_otp
    → OTP dari sink → verify → akun jadi

Mode:
  --mode e2e        : satu akun, tunggu OTP dari sink file (default)
  --mode solve      : satu akun sampai layar captcha, tulis captcha context
  --headless=false  : ada layar (butuh X/screenshare di VPS)
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.accounts import AccountGen
from tools.proxy import ManualOTP, HTTPOTP

BASE = "https://shopee.co.id"
SIGNUP = f"{BASE}/buyer/signup"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


class ShopeeAutoReg:
    def __init__(self, headless=True, proxy=None, otp_sink=None, slow=1.0,
                 shot_dir="/root/shopee-farm/shots"):
        self.headless = headless
        self.proxy = proxy
        self.otp = otp_sink or ManualOTP()
        self.slow = slow
        self.shot_dir = Path(shot_dir)
        self.shot_dir.mkdir(parents=True, exist_ok=True)
        self.captured = {}   # network capture

    # ---------- helpers ----------
    def shot(self, page, tag):
        p = self.shot_dir / f"{tag}_{int(time.time())}.png"
        try:
            page.screenshot(path=str(p), full_page=False)
        except Exception:
            pass
        return str(p)

    def _on_response(self, resp):
        u = resp.url
        if "/api/v4/otp/get_settings_v2" in u:
            try:
                self.captured["get_settings_v2"] = {"status": resp.status, "json": resp.json()}
            except Exception:
                self.captured["get_settings_v2"] = {"status": resp.status}
        elif "/api/v4/otp/send_otp" in u:
            try:
                self.captured["send_otp"] = {"status": resp.status, "json": resp.json()}
            except Exception:
                self.captured["send_otp"] = {"status": resp.status}

    def _on_request(self, req):
        if "/api/v4/otp/" in req.url:
            h = dict(req.headers)
            keep = {k: v for k, v in h.items()
                    if k.lower() in ("x-csrftoken", "af-ac-enc-dat", "x-api-source",
                                     "x-requested-with", "referer", "user-agent")}
            self.captured.setdefault("request_headers", {})[req.url] = keep
            try:
                body = req.post_data
                if body and "get_settings_v2" in req.url:
                    self.captured["get_settings_body"] = json.loads(body)
            except Exception:
                pass

    # ---------- UI steps ----------
    def _dismiss_lang(self, page):
        # Gate "Pilih Bahasa Anda" → tombol "Bahasa Indonesia" / "English"
        for sel in ["text=Bahasa Indonesia", "button:has-text('Bahasa Indonesia')",
                    "text=Oke", "button:has-text('Oke')", "text=English"]:
            try:
                page.click(sel, timeout=5000)
                time.sleep(1.5 * self.slow)
                return True
            except PWTimeout:
                continue
        return False

    def _fill_phone(self, page, phone):
        # Form beda-beda: input bisa type=tel ATAU text/email. Cari yang relevan.
        loc = None
        for sel in ["input[type='tel']", "input[type='text']",
                    "input[placeholder*='Telepon']", "input[placeholder*='onmor']",
                    "input[name*='phone']", "input[type='email']"]:
            try:
                cand = page.locator(sel).first
                if cand.count() and cand.is_visible():
                    loc = cand
                    break
            except Exception:
                continue
        if loc is None:
            # fallback: input pertama yang visible
            loc = page.locator("input:visible").first
        loc.wait_for(state="visible", timeout=15000)
        loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        nat = phone[1:] if phone.startswith("0") else phone
        loc.type(nat, delay=int(60 * self.slow))
        time.sleep(0.6 * self.slow)

    def _check_tos(self, page):
        # ceklis kotak TOS pertama
        for sel in ["input[type='checkbox']", "text=Ketentuan", "[class*='checkbox']"]:
            try:
                els = page.locator(sel)
                if els.count():
                    els.first.click(timeout=4000)
                    return True
            except PWTimeout:
                continue
        return False

    def _next(self, page):
        for sel in ["button:has-text('Berikutnya')", "button:has-text('Next')",
                    "text=Berikutnya"]:
            try:
                page.click(sel, timeout=6000)
                return True
            except PWTimeout:
                continue
        return False

    def _agree_modal(self, page):
        for sel in ["button:has-text('Setuju')", "text=Setuju",
                    "button:has-text('Agree')"]:
            try:
                page.click(sel, timeout=6000)
                return True
            except PWTimeout:
                continue
        return False

    # ---------- main flow ----------
    def register(self, profile, proxy=None):
        px = proxy or self.proxy
        launch_args = {"headless": self.headless,
                       "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]}
        if px:
            launch_args["proxy"] = {"server": px}

        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch_args)
            ctx = browser.new_context(user_agent=UA, locale="id-ID",
                                      viewport={"width": 412, "height": 915},
                                      is_mobile=True, has_touch=True)
            page = ctx.new_page()
            page.on("response", self._on_response)
            page.on("request", self._on_request)

            result = {"phone": profile["phone"], "name": profile["name"], "steps": []}
            try:
                page.goto(SIGNUP, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3 * self.slow)
                result["steps"].append("loaded")
                self.shot(page, "01_loaded")

                if self._dismiss_lang(page):
                    result["steps"].append("lang_dismissed")
                    time.sleep(2 * self.slow)
                self.shot(page, "01b_after_lang")

                # tunggu form (input apapun yang visible) muncul
                try:
                    page.wait_for_selector("input:visible", timeout=15000)
                except PWTimeout:
                    result["steps"].append("no_input")
                    self.shot(page, "01c_no_input")
                    browser.close()
                    return result

                self._fill_phone(page, profile["phone"])
                result["steps"].append("phone_filled")
                time.sleep(1)

                self._check_tos(page)
                time.sleep(0.6)
                self._next(page)
                result["steps"].append("next_clicked")
                time.sleep(2)
                self.shot(page, "02_after_next")

                self._agree_modal(page)
                result["steps"].append("tos_modal_agreed")
                time.sleep(3)

                # tunggu call get_settings_v2 (lebih lama)
                for _ in range(30):
                    if "get_settings_v2" in self.captured:
                        break
                    time.sleep(1)
                result["get_settings_v2"] = self.captured.get("get_settings_v2")
                result["device_fingerprint"] = (self.captured.get("get_settings_body") or {}).get(
                    "client_identifier", {}).get("security_device_fingerprint")
                result["headers"] = self.captured.get("request_headers")
                result["all_api"] = list(self.captured.keys())
                self.shot(page, "03_captcha")
                # simpan incremental — jangan sampai hilang kalau timeout
                try:
                    (self.shot_dir.parent / "auto_reg_result.json").write_text(
                        json.dumps({"profile": profile, "result": result}, indent=2, ensure_ascii=False))
                except Exception:
                    pass

                need_cap = (self.captured.get("get_settings_v2", {}).get("json", {}) or {}).get(
                    "data", {}).get("need_captcha")
                result["need_captcha"] = need_cap

                if need_cap:
                    print("[!] CAPTCHA — mode manual: solve di layar, tunggu send_otp")
                    for _ in range(60):
                        if "send_otp" in self.captured:
                            break
                        time.sleep(1)

                result["send_otp"] = self.captured.get("send_otp")

                # tunggu OTP dari sink
                otp = self.otp.wait(profile["phone"], timeout=180)
                result["otp"] = otp
                result["steps"].append("otp_received" if otp else "otp_timeout")
                self.shot(page, "04_otp")

            except Exception as e:
                result["error"] = f"{type(e).__name__}: {e}"
                self.shot(page, "99_error")
            finally:
                browser.close()
            return result


def main():
    ap = argparse.ArgumentParser(description="Shopee auto-register (Playwright)")
    ap.add_argument("--mode", choices=["e2e", "solve"], default="e2e")
    ap.add_argument("--headless", default="true")
    ap.add_argument("--phone", help="nomor uji (default: generate)")
    ap.add_argument("--proxy", help="http://user:pass@host:port")
    ap.add_argument("--slow", type=float, default=1.0)
    args = ap.parse_args()

    gen = AccountGen()
    profile = gen.profile()
    if args.phone:
        profile["phone"] = args.phone
    print("profile:", json.dumps({k: profile[k] for k in ("name", "phone")}, ensure_ascii=False))

    otp = ManualOTP("/root/shopee-farm/otp.txt")
    reg = ShopeeAutoReg(headless=(args.headless.lower() == "true"),
                        proxy=args.proxy, otp_sink=otp, slow=args.slow)
    out = reg.register(profile, proxy=args.proxy)
    print(json.dumps(out, indent=2, ensure_ascii=False))

    save = Path("/root/shopee-farm/auto_reg_result.json")
    save.write_text(json.dumps({"profile": profile, "result": out}, indent=2, ensure_ascii=False))
    print("saved:", save)


if __name__ == "__main__":
    main()
