#!/usr/bin/env python3
"""shopee_api_signup.py — FULL PURE-API signup (tanpa browser).
Reverse dari bundle SignupByOTP.js + shopee.py reference.

Flow (1 sesi cookie):
  1. warmup GET /buyer/signup → set csrftoken, fingerprint
  2. POST /api/v4/otp/send_vcode   {phone, channel, operation:0}
  3. POST /api/v4/otp/verify_vcode {vcode, support_session:True, operation:8,
                                    phone, m_token, vcode_token,
                                    client_identifier:{security_device_fingerprint}}
     → balikin otp_token
  4. POST /api/v4/account/signup_by_otp {otp_token, password(sha256(md5)), ...}
  5. POST /api/v4/account/basic/get_account_info → userId
"""
import requests, json, sys, re, time, hashlib, uuid, os
import urllib3
urllib3.disable_warnings()

PROXY = "http://127.0.0.1:8888"  # via mitmproxy (capture) → upstream VS proxy
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


class ShopeeAPI:
    def __init__(self, phone, proxy=PROXY):
        p = phone.lstrip("+").lstrip("0")
        self.phone = p
        self.s = requests.Session()
        self.s.proxies = {"http": proxy, "https": proxy}
        self.s.verify = False
        self.s.headers.update({
            "User-Agent": UA,
            "Accept": "application/json",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
            "Origin": "https://shopee.co.id",
            "Referer": "https://shopee.co.id/buyer/signup",
            "x-api-source": "pc",
            "x-requested-with": "XMLHttpRequest",
            "x-shopee-language": "id",
            "Content-Type": "application/json",
        })
        self.fp = "%s|%s|%s|08|1" % (uuid.uuid4().hex[:16],
                                     uuid.uuid4().hex[:16], uuid.uuid4().hex[:16])
        self.vcode_token = ""
        self.m_token = ""

    def log(self, *a): print(*a, flush=True)

    def _j(self, r):
        try: return r.json()
        except Exception: return {"_raw": r.text[:250]}

    def _post(self, path, body):
        r = self.s.post("https://shopee.co.id" + path, json=body, timeout=40)
        return r.status_code, self._j(r)

    def warmup(self):
        self.log("[1] warmup /buyer/signup")
        r = self.s.get("https://shopee.co.id/buyer/signup", timeout=45)
        self.log("    ", r.status_code, "cookies:", list(self.s.cookies.keys()))
        ct = self.s.cookies.get("csrftoken")
        if not ct:
            m = re.search(r'csrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)', r.text)
            ct = m.group(1) if m else ""
        if ct:
            self.s.headers["x-csrftoken"] = ct
            self.log("    csrf:", ct[:24])
        self.s.cookies.set("shopee_webUnique_ccd", self.fp, domain=".shopee.co.id")
        return ct

    def send_vcode(self, channel=1, operation=0):
        self.log(f"[2] send_vcode ch={channel} op={operation}")
        st, j = self._post("/api/v4/otp/send_vcode", {
            "phone": self.phone, "channel": channel, "operation": operation,
            "force_channel": False, "m_token": ""})
        self.log("    ", st, json.dumps(j)[:220])
        d = (j or {}).get("data") or {}
        self.vcode_token = d.get("otp_tracking_id") or d.get("seed") or ""
        return j

    def verify_vcode(self, vcode, operation=8):
        self.log(f"[3] verify_vcode {vcode} op={operation}")
        st, j = self._post("/api/v4/otp/verify_vcode", {
            "vcode": vcode,
            "support_session": True,
            "operation": operation,
            "phone": self.phone,
            "m_token": self.m_token,
            "vcode_token": self.vcode_token,
            "client_identifier": {"security_device_fingerprint": self.fp},
        })
        self.log("    ", st, json.dumps(j)[:280])
        d = (j or {}).get("data") or {}
        tok = d.get("vcode_token") or d.get("otp_token") or d.get("request_id") or self.vcode_token
        return j, tok

    @staticmethod
    def hash_pw(pw):
        return hashlib.sha256(hashlib.md5(pw.encode()).hexdigest().encode()).hexdigest()

    def signup(self, password, otp_token):
        self.log("[4] signup_by_otp")
        st, j = self._post("/api/v4/account/signup_by_otp", {
            "otp_token": otp_token,
            "password": self.hash_pw(password),
            "stay_logged_in": True,
            "client_identifier": {"security_device_fingerprint": self.fp},
        })
        self.log("    ", st, json.dumps(j)[:280])
        return j

    def account_info(self):
        self.log("[5] get_account_info")
        st, j = self._post("/api/v4/account/basic/get_account_info", {})
        self.log("    ", st, json.dumps(j)[:300])
        return j

    def cookies(self):
        return {c.name: c.value for c in self.s.cookies}


if __name__ == "__main__":
    phone = sys.argv[1] if len(sys.argv) > 1 else "6285849156988"
    cmd = sys.argv[2] if len(sys.argv) > 2 else "send"
    api = ShopeeAPI(phone)
    api.warmup()
    if cmd == "send":
        api.send_vcode(channel=1, operation=0)
    elif cmd == "verify":
        code = sys.argv[3]
        api.send_vcode(channel=1, operation=0)
        time.sleep(6)
        j, tok = api.verify_vcode(code)
        if (j or {}).get("error") == 0:
            api.signup("PASS_REDACTED", tok)
            api.account_info()
            print("COOKIES:", json.dumps(api.cookies())[:400], flush=True)
