---
name: shopee-sms-otp-bypass
description: "Register Shopee accounts via SMS OTP, no captcha."
---

# Shopee SMS-OTP Captcha Bypass

The OTP/SMS signup flow uses DIFFERENT endpoints than the web signup form. The web form hits `get_settings_v2` and gets `need_captcha: true` (slide puzzle). The SMS/OTP path hits `send_vcode` directly and gets `need_captcha: FALSE` — no puzzle, no solver.

## Verified endpoints (shopee.co.id, LIVE tested)

All base: `https://shopee.co.id`

| Path | Method | Body | Result |
|------|--------|------|--------|
| `/api/v4/otp/get_settings_v2` | POST | `{phone, operation:0, channel:1}` | `need_captcha: FALSE`, `captcha_scene:"others"`, `available_channels:[1]`, `seed` |
| `/api/v4/otp/send_vcode` | POST | `{phone, channel:1, operation:0, force_channel:false, m_token:""}` | `error:0`, `otp_tracking_id` (== seed), `delivery_channel:1` |
| `/api/v4/otp/verify_vcode` | POST | `{phone, code:<OTP>, operation:0}` | `error:0` if code valid |
| `/api/v4/account/signup_by_otp` | POST | `{otp_token, password, stay_logged_in:true, client_identifier:{security_device_fingerprint:""}}` | creates account |
| `/api/v4/account/basic/check_phone_exist` | POST | `{phone}` | 403 error=90309999 (needs anti-fraud token — OPTIONAL, skip it) |

`channel`: 1 = SMS, 2 = WhatsApp (verify per number).
`operation`: 0 = signup.

## Required headers

```
User-Agent: Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36
Accept: application/json, text/plain, */*
Origin: https://shopee.co.id
Referer: https://shopee.co.id/buyer/signup
x-api-source: pc
x-requested-with: XMLHttpRequest
x-shopee-language: id
Content-Type: application/json
```

Direct connection to shopee.co.id works (200) from some VPS — no proxy needed for the OTP path.

## Critical flow rule — SEED CONSISTENCY

**Every `send_vcode` call issues a NEW `otp_tracking_id` (seed). The previous code becomes INVALID.**

Correct sequence:
1. `send_vcode` → save `otp_tracking_id` as `seed`
2. User reads OTP from the LATEST SMS
3. `verify_vcode {phone, code, operation:0}` — do NOT send between step 1 and 3

Errors:
- `23500000` = code mismatch/wrong
- `23500002` = code expired or seed superseded (a new send happened)
- `90309999` = anti-fraud token missing (only on check_phone_exist)

## Minimal working flow

```python
import requests
S=requests.Session(); S.verify=False
S.headers.update({"User-Agent":"Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36","Accept":"application/json, text/plain, */*","Origin":"https://shopee.co.id","Referer":"https://shopee.co.id/buyer/signup","x-api-source":"pc","x-requested-with":"XMLHttpRequest","x-shopee-language":"id","Content-Type":"application/json"})
S.get("https://shopee.co.id/buyer/signup",timeout=45)  # warmup
r=S.post("https://shopee.co.id/api/v4/otp/send_vcode",json={"phone":"6289xxxx","channel":1,"operation":0,"force_channel":False,"m_token":""},timeout=45)
seed=r.json()["data"]["otp_tracking_id"]
# ... user provides OTP ...
S.post("https://shopee.co.id/api/v4/otp/verify_vcode",json={"phone":"6289xxxx","code":"123456","operation":0},timeout=45)
```

## Why this matters for scale

- No browser render → no Playwright → no residential proxy needed
- No captcha solver → no SadCaptcha API cost for signup
- Pure HTTP, fast — scales to 50+/day easily

## Bot integration (shopee-war)

- Module: `/root/shopee-war/sms_signup.py` — `normalize_phone`, `hash_password`, `SmsSession`, `SmsFlow`.
- Menu button: `📲 Regis SMS (Bypass Captcha)` → callback `m_smsreg`.
- Flow states: `smsreg_phone` (enter number) → `smsreg_channel` (pick SMS/WA via `smsreg_ch:1|2`) → `smsreg_wait_otp` (paste code) → verify + `signup_by_otp`.
- Bot: `@my_update_otpbot` (id 8903646663), service `shopee-war.service`.

## Verified live (2026-10-17)

- `get_settings_v2` on SMS path returns `need_captcha: false` — captcha bypass CONFIRMED.
- `send_vcode` channel=1 returns `error:0`, OTP delivered.
- `verify_vcode` on a fresh send+code pair is the only working sequence; a second `send_vcode` invalidates the prior code (`23500002`).
- VPS direct connection to shopee.co.id works (200) — no proxy needed for OTP path.

- `verify_vcode` body key is `code`, not `otp`/`vcode`.
- `check_phone_exist` 403 is harmless — skip it.
- fingerprint (`security_device_fingerprint`) can be empty string `""` for signup_by_otp.
