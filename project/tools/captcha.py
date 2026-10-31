"""Captcha solver adapter for Shopee signup.

⚠️ KOREKSI (2026-10-14): captcha Shopee BUKAN reCAPTCHA/geetest pihak-3.
   Ini captcha KUSTOM Shopee — div id="anti_fraud_captcha", di-serve dari
   deo.shopeemobile.com/shopee/captcha/. Endpoint:
     /api/v4/anti_fraud/captcha/get_config
     /api/v4/anti_fraud/captcha/generate
     /api/v4/anti_fraud/captcha/feedback/questions

   → solver umum (2captcha/capsolver) TIDAK punya task type untuk ini.
   → butuh reverse bundle OR hook CDP di browser (baca challenge + kirim jawaban).

Modul ini menyediakan INTERFACE + stub; implementasi jawab-captcha-shopee
dilakukan via hook Playwright CDP (lihat captcha_hook.py), bukan API solver.
"""
import os

# Env opsional — kalau nanti ada provider yang dukung captcha Shopee kustom.
PROVIDER = os.environ.get("CAP_SOLVER", "")
API_KEY = os.environ.get("CAP_API_KEY", "")


class SolverBase:
    """Interface. Untuk Shopee kustom, `solve_custom` yang relevan."""
    def solve_custom(self, challenge: dict, url: str) -> dict | None:
        raise NotImplementedError


class ShopeeCaptchaHook(SolverBase):
    """Jawab captcha kustom Shopee via hook browser (CDP/JS).

    Alur: baca payload challenge dari /anti_fraud/captcha/generate,
    selesaikan (klik objek / drag), POST jawaban ke /captcha/.../feedback.
    TIDAK pakai API pihak-3 — semua di dalam konteks browser Playwright.
    """
    def solve_custom(self, challenge, url):
        # diimplementasikan di auto_reg.py / farm_browser.py via page.evaluate
        raise NotImplementedError(
            "captcha Shopee kustom — jawab via hook browser, bukan API solver")


def get_solver() -> SolverBase:
    return ShopeeCaptchaHook()

