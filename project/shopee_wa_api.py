#!/usr/bin/env python3
"""shopee_wa_api.py — WA signup via API + riskToken dari shpsec report.
Flow:
  1. warmup → shpsec report → dapet riskToken (pengganti captcha, otomatis)
  2. get_settings_v2 {op:8} → channels [3,2,1]
  3. send_vcode {ch:3, op:8, m_token:<riskToken>}  → WA terkirim
  4. verify_vcode {vcode, op:8, support_session}
  5. signup_by_otp
"""
import requests, json, sys, re, time, hashlib, uuid
import urllib3
urllib3.disable_warnings()

PROXY = "http://127.0.0.1:8888"   # via mitm (capture) -> upstream VS proxy

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


class ShopeeWA:
    def __init__(self, phone, proxy=PROXY):
        self.phone = phone
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
        self.risk_token = ""
        self.vcode_token = ""

    def log(self, *a): print(*a, flush=True)

    def _j(self, r):
        try: return r.json()
        except Exception: return {"_raw": r.text[:250]}

    def _post(self, path, body, host="https://shopee.co.id"):
        r = self.s.post(host + path, json=body, timeout=45)
        return r.status_code, self._j(r)

    def warmup(self):
        self.log("[1] warmup + shpsec report")
        r = self.s.get("https://shopee.co.id/buyer/signup", timeout=45)
        ct = self.s.cookies.get("csrftoken") or ""
        if not ct:
            m = re.search(r'csrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)', r.text)
            ct = m.group(1) if m else ""
        if ct: self.s.headers["x-csrftoken"] = ct
        self.s.cookies.set("shopee_webUnique_ccd", self.fp, domain=".shopee.co.id")
        self.log("    ", r.status_code, "cookies:", list(self.s.cookies.keys()))

    def shpsec_report(self):
        """beacon anti-fraud → riskToken (pengganti captcha)."""
        self.log("[2] shpsec report → riskToken")
        try:
            r = self.s.post("https://df.infra.sz.shopee.co.id/v2/shpsec/web/report",
                            data="JxcBAAAABAAAAIAAAD", timeout=30,
                            headers={"Content-Type": "text/plain;charset=UTF-8"})
            j = self._j(r)
            self.risk_token = ((j.get("data") or {}).get("riskToken") or "")
            self.log("    ", r.status_code, "riskToken:", self.risk_token[:50] or "(none)")
        except Exception as e:
            self.log("    ERR", str(e)[:100])

    def get_settings(self, operation=8):
        self.log(f"[3] get_settings_v2 op={operation}")
        st, j = self._post("/api/v4/otp/get_settings_v2",
                           {"phone": self.phone, "operation": operation})
        d = (j or {}).get("data") or {}
        self.log("    ", st, "channels:", d.get("available_channels"),
                 "need_captcha:", d.get("need_captcha"))
        return j

    def send_vcode(self, channel=3, operation=8):
        self.log(f"[4] send_vcode ch={channel} op={operation}")
        st, j = self._post("/api/v4/otp/send_vcode", {
            "phone": self.phone, "channel": channel, "operation": operation,
            "force_channel": True, "m_token": self.risk_token})
        self.log("    ", st, json.dumps(j)[:230])
        d = (j or {}).get("data") or {}
        self.vcode_token = d.get("otp_tracking_id") or d.get("seed") or ""
        return j

    def verify_vcode(self, vcode, operation=8):
        self.log(f"[5] verify_vcode {vcode}")
        st, j = self._post("/api/v4/otp/verify_vcode", {
            "vcode": vcode, "support_session": True, "operation": operation,
            "phone": self.phone, "m_token": self.risk_token,
            "vcode_token": self.vcode_token,
            "client_identifier": {"security_device_fingerprint": self.fp}})
        self.log("    ", st, json.dumps(j)[:250])
        d = (j or {}).get("data") or {}
        return j, (d.get("vcode_token") or d.get("otp_token") or self.vcode_token)

    @staticmethod
    def hash_pw(pw):
        return hashlib.sha256(hashlib.md5(pw.encode()).hexdigest().encode()).hexdigest()

    def signup(self, password, otp_token):
        self.log("[6] signup_by_otp")
        st, j = self._post("/api/v4/account/signup_by_otp", {
            "otp_token": otp_token, "password": self.hash_pw(password),
            "stay_logged_in": True,
            "client_identifier": {"security_device_fingerprint": self.fp}})
        self.log("    ", st, json.dumps(j)[:250])
        return j

    def account_info(self):
        st, j = self._post("/api/v4/account/basic/get_account_info", {})
        self.log("[7] account_info", st, json.dumps(j)[:250])
        return j

    def cookies(self):
        return {c.name: c.value for c in self.s.cookies}


if __name__ == "__main__":
    phone = sys.argv[1] if len(sys.argv) > 1 else "6287876125616"
    mode = sys.argv[2] if len(sys.argv) > 2 else "send"
    w = ShopeeWA(phone)
    w.warmup()
    w.shpsec_report()
    w.get_settings(8)
    if mode == "send":
        w.send_vcode(3, 8)
    elif mode == "verify":
        code = sys.argv[3]
        w.send_vcode(3, 8)
        if w.vcode_token:
            print(">>> kirim kode ke verify: pakai sesi ini", flush=True)
