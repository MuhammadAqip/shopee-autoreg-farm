"""Shopee registration client — endpoint VERIFIED against live server (sniff A).

Chain (terekam dari shopee.co.id/buyer/signup, lihat SNIFF_A_RESULTS.md):

  1. GET  /buyer/signup              -> cookies + csrftoken (SPC_F, SPC_U)
  2. POST /api/v4/otp/get_settings_v2-> cek channel + whether captcha needed
  3. [captcha]  slider puzzle (geetest-style)   -> token
  4. POST /api/v4/otp/send_otp       -> kirim OTP ke HP (butuh token captcha)
  5. POST /api/v4/account/...verify  -> OTP + password -> akun dibuat
  6. POST /api/v4/account/login_by_password -> session token

HARD BOUNDARY (terverifikasi):
  - `security_device_fingerprint` & `af-ac-enc-dat` di-generate client-side oleh
    bundle browser-signals. Tanpa JS/hook, request akan ditolak (Cloudflare 502 /
    need_captcha). Lihat frida_shopee_signup.js untuk cara ambil nilai asli.
  - Captcha slider WAJIB diselesaikan (solver ATAU token dari sesi browser nyata).

Setiap step device-bound. Klien pakai SATU Device + SATU cookie jar per chain;
IP dirotasi antar-akun (proxy), bukan di tengah chain.
"""
import base64
import json
import random
import time
import requests
from http.cookies import SimpleCookie

from .device import Device


BASE = "https://shopee.co.id"


class ShopeeClient:
    def __init__(self, device: Device = None, proxy: str = None, timeout: int = 25):
        self.device = device or Device()
        self.proxy = proxy
        self.timeout = timeout
        self.csrf = None
        self.session = requests.Session()
        self.session.headers.update(self._headers())

    # ---------- headers (VERIFIED — lihat sniff) ----------
    def _headers(self) -> dict:
        d = self.device
        return {
            # header web asli (bukan app) — x-api-source: rweb
            "User-Agent": d.user_agent(),
            "Accept": "application/json",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
            "X-API-SOURCE": "rweb",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
            "Referer": f"{BASE}/buyer/signup",
            "Origin": BASE,
            "af-ac-enc-dat": self._afac_placeholder(),
            "Connection": "keep-alive",
        }

    def _afac_placeholder(self) -> str:
        """`af-ac-enc-dat` = 16-hex per-request token (terenkripsi).
        Placeholder 16 hex; nilai valid butuh bundle browser-signals / hook Frida."""
        return base64.b16encode(bytes(random.getrandbits(8) for _ in range(8))).decode().lower()

    def _proxies(self):
        if not self.proxy:
            return None
        return {"http": self.proxy, "https": self.proxy}

    def _apply_cookies(self, resp):
        sc = resp.headers.get("Set-Cookie")
        if sc:
            c = SimpleCookie()
            try:
                c.load(sc)
                for k, m in c.items():
                    self.session.cookies.set(k, m.value, domain=".shopee.co.id")
            except Exception:
                pass

    def _post(self, path: str, payload: dict) -> dict:
        r = self.session.post(f"{BASE}{path}", json=payload,
                              proxies=self._proxies(), timeout=self.timeout)
        self._apply_cookies(r)
        return self._parse(r)

    # ---------- chain ----------
    def warm_up(self) -> dict:
        """Step 1 — GET /buyer/signup, panen cookie + csrftoken."""
        r = self.session.get(f"{BASE}/buyer/signup", proxies=self._proxies(),
                             timeout=self.timeout, allow_redirects=True)
        self._apply_cookies(r)
        csrf = self.session.cookies.get("csrftoken") or self._extract_csrf(r.text)
        if csrf:
            self.csrf = csrf
            self.session.headers["X-CSRFToken"] = csrf
        return {
            "status": r.status_code,
            "csrf": bool(csrf),
            "spc_f": self.session.cookies.get("SPC_F"),
            "cookies": list(self.session.cookies.keys()),
        }

    @staticmethod
    def _extract_csrf(html: str):
        import re
        m = re.search(r'name="csrf-?token"\s+value="([^"]+)"', html or "")
        if m:
            return m.group(1)
        m = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', html or "")
        return m.group(1) if m else None

    # ---- VERIFIED endpoint: /api/v4/otp/get_settings_v2 ----
    def get_otp_settings(self, phone: str) -> dict:
        """Step 2 — cek channel OTP + apakah captcha dibutuhkan.

        Payload asli (terekam): operation, phone (62xxx), supported_channels,
        support_session, client_identifier.security_device_fingerprint.
        """
        payload = {
            "operation": 8,
            "encrypted_phone": "",
            "phone": self._norm_phone(phone),
            "supported_channels": [1, 2, 3, 6, 0, 5],
            "support_session": True,
            "client_identifier": {
                # nilai asli = token terenkripsi dari bundle browser-signals.
                # placeholder: butuh Frida/hook untuk yang valid.
                "security_device_fingerprint": self._fp_placeholder(),
            },
        }
        out = self._post("/api/v4/otp/get_settings_v2", payload)
        data = out.get("body", {}).get("data") or {}
        out["need_captcha"] = data.get("need_captcha")
        out["captcha_scene"] = data.get("captcha_scene")
        out["seed"] = (data.get("session_info") or {}).get("seed")
        return out

    def _fp_placeholder(self) -> str:
        b64 = lambda n: base64.b64encode(bytes(random.getrandbits(8) for _ in range(n))).decode()
        return f"{b64(24)}|{b64(56)}|{b64(12)}"

    # ---- send OTP (butuh token captcha kalau need_captcha=true) ----
    def send_otp(self, phone: str, captcha_token: str = None) -> dict:
        """Step 3/4 — minta OTP. Kalau need_captcha, sertakan captcha_token dari solver."""
        payload = {
            "phone": self._norm_phone(phone),
            "country_code": "62",
            "supported_channels": [1, 2, 3],
            "support_session": True,
            "operation": 8,
            "client_identifier": {"security_device_fingerprint": self._fp_placeholder()},
        }
        if captcha_token:
            payload["captcha_token"] = captcha_token
        return self._post("/api/v4/otp/send_otp", payload)

    # ---- verify OTP + buat akun ----
    def verify_otp(self, phone: str, otp: str, password: str, name: str,
                   captcha_token: str = None) -> dict:
        payload = {
            "phone": self._norm_phone(phone),
            "country_code": "62",
            "otp": otp,
            "password": password,
            "name": name,
            "client_identifier": {"security_device_fingerprint": self._fp_placeholder()},
        }
        if captcha_token:
            payload["captcha_token"] = captcha_token
        return self._post("/api/v4/account/verify_otp", payload)

    # ---- VERIFIED endpoint: /api/v4/account/login_by_password ----
    def login(self, phone: str, password: str) -> dict:
        """Step 6 — session token. Path divalidasi 200 oleh server (sniff)."""
        payload = {
            "phone": self._norm_phone(phone),
            "country_code": "62",
            "password": password,
            "client_identifier": {"security_device_fingerprint": self._fp_placeholder()},
        }
        out = self._post("/api/v4/account/login_by_password", payload)
        data = out.get("body", {}).get("data")
        token = data.get("access_token") if isinstance(data, dict) else None
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        return out

    # ---------- helpers ----------
    @staticmethod
    def _norm_phone(phone: str) -> str:
        """08xxx / +628xxx / 8xxx  ->  628xxx"""
        p = "".join(ch for ch in phone if ch.isdigit())
        if p.startswith("0"):
            p = p[1:]
        if not p.startswith("62"):
            p = "62" + p
        return p

    @staticmethod
    def _parse(r) -> dict:
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text[:400]}
        return {"http": r.status_code, "body": body}

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
