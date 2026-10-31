#!/usr/bin/env python3
"""otp_policy.py — #9: kebijakan resend OTP otomatis + deteksi cooldown.

Baca `remaining_resend_cooldown_sec` dari get_settings_v2, tunggu kalau perlu,
lalu resend via otp_resend (API). Dipakai bot utk auto-resend tanpa intervensi.

Fungsi utama:
  check_cooldown(session_or_page, phone) -> {"cooldown": N, "channels":[...]}
  auto_resend(phone, max_tries=3)  -> kirim ulang OTP dgn backoff sampai sukses/limit
"""
import os, sys, time, json
import requests

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))
BASE = "https://shopee.co.id/api/v4/otp"


def _sess(proxy=None):
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                      "accept": "application/json", "x-api-source": "pc",
                      "x-requested-with": "XMLHttpRequest", "x-shopee-language": "id",
                      "referer": "https://shopee.co.id/buyer/signup"})
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    return s


def read_cooldown(resp_json):
    """Ambil cooldown dari response get_settings_v2."""
    d = (resp_json or {}).get("data") or {}
    si = d.get("session_info") or {}
    return {"cooldown": si.get("remaining_resend_cooldown_sec", 0),
            "switch_cd": si.get("remaining_switch_cooldown_sec", 0),
            "channels": d.get("available_channels"), "preferred": d.get("preferred_channel"),
            "need_captcha": d.get("need_captcha")}


def auto_resend(phone, proxy=None, max_tries=3, log=print):
    """Strategy resend: tunggu cooldown → tembak send_vcode per channel dgn backoff."""
    s = _sess(proxy)
    if not phone.startswith("62"):
        phone = "62" + phone.lstrip("+0")
    last = {}
    for i in range(max_tries):
        try:
            r = s.post(f"{BASE}/get_settings_v2", json={
                "operation": 8, "phone": phone, "supported_channels": [1, 2, 3, 6, 0, 5],
                "support_session": True, "client_identifier": {"security_device_fingerprint": ""}}, timeout=30)
            j = r.json()
        except Exception as e:
            log(f"[policy] get_settings err {str(e)[:60]}"); time.sleep(2); continue
        cd = read_cooldown(j)
        log(f"[policy] try{i+1}: cooldown={cd['cooldown']}s channels={cd['channels']}")
        if cd["cooldown"] and cd["cooldown"] > 0:
            wait = min(cd["cooldown"] + 1, 60)
            log(f"[policy] tunggu {wait}s (cooldown)")
            time.sleep(wait)
        for ch in ([3, 1, 2] if cd.get("preferred") != 1 else [1, 3, 2]):
            try:
                rr = s.post(f"{BASE}/send_vcode", json={
                    "channel": ch, "operation": 8, "phone": phone, "m_token": "",
                    "supported_channels": [1, 2, 3, 6, 0, 5],
                    "client_identifier": {"security_device_fingerprint": ""}}, timeout=30)
                jj = rr.json()
                err = jj.get("error")
                last = {"channel": ch, "error": err}
                log(f"[policy] send_vcode ch{ch} → {err}")
                if err == 0:
                    return {"ok": True, "channel": ch}
                if err == 23500101:   # butuh captcha token
                    return {"ok": False, "need_captcha": True, "channel": ch}
                if err == 23500152:   # rate-limited → backoff
                    time.sleep(5 + i * 5); break
            except Exception as e:
                log(f"[policy] send err {str(e)[:50]}")
        time.sleep(2 + i * 3)
    return {"ok": False, "last": last}


if __name__ == "__main__":
    ph = sys.argv[1] if len(sys.argv) > 1 else "6285353984860"
    print(auto_resend(ph))
