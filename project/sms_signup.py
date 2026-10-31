#!/usr/bin/env python3
"""sms_signup.py — Shopee signup via SMS/OTP (BYPASS CAPTCHA).

Flow (TERBUKTI LIVE — need_captcha:false di jalur SMS):
  1. warmup   GET  /buyer/signup
  2. settings POST /api/v4/otp/get_settings_v2   -> need_captcha:false
  3. send     POST /api/v4/otp/send_vcode        -> OTP SMS terkirim
  4. verify   POST /api/v4/otp/verify_vcode      -> error:0 kalau kode benar
  5. daftar   POST /api/v4/account/signup_by_otp -> akun jadi

PENTING (SEED CONSISTENCY):
  Tiap send_vcode bikin otp_tracking_id BARU. Kode lama jadi invalid.
  Jangan panggil send 2x sebelum verify.

Endpoint check_phone_exist 403 = butuh anti-fraud token (opsional, skip).

Session & session continuity: dipakai object SmsSession yg menyimpan cookie
persisten supaya verify ke-link dengan seed kiriman.
"""
import re
import os
import json
import time
import hashlib
import threading

try:
    import requests
    _HAS_REQ = True
except Exception:
    _HAS_REQ = False

BASE = "https://shopee.co.id"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Origin": BASE,
    "Referer": BASE + "/buyer/signup",
    "x-api-source": "pc",
    "x-requested-with": "XMLHttpRequest",
    "x-shopee-language": "id",
    "Content-Type": "application/json",
}


def normalize_phone(p: str) -> str:
    """08xxx / 8xxx / +628xxx -> 628xxx"""
    p = re.sub(r"[^\d+]", "", p or "")
    if p.startswith("+62"):
        p = p[1:]
    if p.startswith("0"):
        p = "62" + p[1:]
    elif p.startswith("8"):
        p = "62" + p
    return p


def hash_password(password: str) -> str:
    """Shopee: sha256(md5(password)) hex."""
    md5h = hashlib.md5(password.encode()).hexdigest()
    return hashlib.sha256(md5h.encode()).hexdigest()


class SmsSession:
    """Sesi HTTP persisten untuk flow OTP SMS."""

    def __init__(self, proxy: str = None, timeout: int = 45, cookie_file: str = None):
        if not _HAS_REQ:
            raise RuntimeError("requests tidak terpasang")
        self.timeout = timeout
        self.cookie_file = cookie_file
        self.s = requests.Session()
        self.s.verify = False
        try:
            import urllib3
            urllib3.disable_warnings()
        except Exception:
            pass
        if proxy:
            self.s.proxies = {"http": proxy, "https": proxy}
        self.s.headers.update(HEADERS)
        self.seed = None
        self.phone = None
        if cookie_file:
            self._load_cookies()

    def _load_cookies(self):
        try:
            import json as _j
            from http.cookies import SimpleCookie
            if os.path.exists(self.cookie_file):
                data = _j.load(open(self.cookie_file))
                for k, v in (data.get("cookies") or {}).items():
                    self.s.cookies.set(k, v)
                self.seed = data.get("seed")
                self.phone = data.get("phone")
        except Exception:
            pass

    def _save_cookies(self):
        if not self.cookie_file:
            return
        try:
            import json as _j
            _j.dump({"cookies": self.s.cookies.get_dict(),
                     "seed": self.seed, "phone": self.phone},
                    open(self.cookie_file, "w"))
        except Exception:
            pass

    def _post(self, path, body):
        r = self.s.post(BASE + path, json=body, timeout=self.timeout)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"_raw": r.text[:400]}

    def warmup(self):
        """GET signup page -> tanam cookie (termasuk csrftoken)."""
        try:
            r = self.s.get(BASE + "/buyer/signup", timeout=self.timeout)
            csrf = self.s.cookies.get("csrftoken") or self.s.cookies.get("csrf_token")
            if not csrf:
                m = re.search(r'csrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)', r.text)
                if m:
                    csrf = m.group(1)
            if csrf:
                self.s.headers["x-csrftoken"] = csrf
            return {"status": r.status_code, "csrf": bool(csrf),
                    "cookies": list(self.s.cookies.keys())}
        except Exception as e:
            return {"status": -1, "err": str(e)[:150]}

    def get_settings(self, phone):
        return self._post("/api/v4/otp/get_settings_v2",
                          {"phone": phone, "operation": 0, "channel": 1})

    def send_otp(self, phone, channel=1):
        """channel: 1=SMS, 2=WhatsApp. Return dict + simpan seed."""
        self.phone = phone
        st, js = self._post("/api/v4/otp/send_vcode",
                            {"phone": phone, "channel": channel,
                             "operation": 0, "force_channel": False, "m_token": ""})
        if isinstance(js, dict) and js.get("data"):
            self.seed = js["data"].get("otp_tracking_id") or js["data"].get("seed")
        self._save_cookies()
        return st, js

    def verify_otp(self, phone, code):
        """Verify kode. TIDAK boleh ada send di antaranya."""
        bodies = [
            {"phone": phone, "code": str(code), "operation": 0},
        ]
        for b in bodies:
            st, js = self._post("/api/v4/otp/verify_vcode", b)
            if isinstance(js, dict) and js.get("error") == 0:
                return st, js
        return st, js

    def signup(self, password, otp_token="", fingerprint=""):
        """Daftar setelah OTP verified."""
        body = {
            "otp_token": otp_token or "",
            "password": hash_password(password) if not _is_hashed(password) else password,
            "stay_logged_in": True,
            "client_identifier": {"security_device_fingerprint": fingerprint or ""},
        }
        return self._post("/api/v4/account/signup_by_otp", body)


def _is_hashed(p: str) -> bool:
    return bool(p) and len(p) == 64 and all(c in "0123456789abcdef" for c in p.lower())


ERR = {
    0: "OK",
    90309999: "butuh anti-fraud token (skip endpoint ini)",
    23500000: "kode OTP salah/mismatch",
    23500002: "kode expired / sesi tidak sinkron (ada send baru?)",
    23500158: "rate-limited: Shopee sedang menangani (tunggu 15-30 menit)",
    23500101: "phone invalid",
    23500153: "channel tidak tersedia untuk nomor ini",
}


def explain(err_code):
    return ERR.get(err_code, f"error {err_code}")


# ---- helper level-bot: state machine ----
class SmsFlow:
    """Flow lengkap utk dipakai bot — 4 langkah, dijaga per chat_id."""

    def __init__(self, phone, proxy=None, password=None, cookie_file=None):
        self.phone = normalize_phone(phone)
        self.cookie_file = cookie_file or f"/tmp/smsflow_{self.phone}.json"
        self.sess = SmsSession(proxy=proxy, cookie_file=self.cookie_file)
        self.password = password or ("Shp" + str(int(time.time()))[-6:] + "Aa1")
        self.otp_token = ""
        self.step = "init"
        self.verified = False

    @classmethod
    def rebuild(cls, phone, proxy=None, password=None, cookie_file=None):
        """Rebuild flow dari cookie tersimpan (setelah bot restart)."""
        f = cls(phone, proxy=proxy, password=password, cookie_file=cookie_file)
        f.step = "sent" if f.sess.seed else "init"
        return f

    def step_send(self, channel=1):
        self.sess.warmup()
        st, js = self.sess.get_settings(self.phone)
        if isinstance(js, dict) and js.get("data"):
            nc = js["data"].get("need_captcha")
            self.step = "settings"
            self._settings = js
        st, js = self.sess.send_otp(self.phone, channel=channel)
        if isinstance(js, dict) and js.get("error") == 0:
            self.step = "sent"
            return {"ok": True, "seed": self.sess.seed, "channel": channel,
                    "data": js.get("data")}
        return {"ok": False, "error": js.get("error") if isinstance(js, dict) else None,
                "msg": explain(js.get("error", -1)) if isinstance(js, dict) else "gagal"}

    def step_verify(self, code):
        st, js = self.sess.verify_otp(self.phone, code)
        if isinstance(js, dict) and js.get("error") == 0:
            self.verified = True
            self.step = "verified"
            # otp_token biasanya di data
            d = js.get("data") or {}
            self.otp_token = d.get("otp_token") or d.get("token") or ""
            return {"ok": True, "data": d}
        code_err = js.get("error") if isinstance(js, dict) else -1
        return {"ok": False, "error": code_err, "msg": explain(code_err)}

    def step_signup(self, password=None):
        if not self.verified:
            return {"ok": False, "msg": "OTP belum diverifikasi"}
        pw = password or self.password
        st, js = self.sess.signup(pw, otp_token=self.otp_token)
        if isinstance(js, dict) and js.get("error") == 0:
            return {"ok": True, "password": pw, "data": js.get("data")}
        code_err = js.get("error") if isinstance(js, dict) else -1
        return {"ok": False, "error": code_err, "msg": explain(code_err)}


if __name__ == "__main__":
    print("sms_signup.py — module. Test manual:")
    print("  s=SmsSession(); s.warmup(); print(s.get_settings('62896xxxx'))")
