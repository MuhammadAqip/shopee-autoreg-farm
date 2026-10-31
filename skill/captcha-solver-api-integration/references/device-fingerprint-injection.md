# Device-fingerprint injection for browser signup farms

Some anti-bot stacks bind signup to a client-computed device fingerprint AND expect
the SAME fingerprint echoed back in API payloads. Two injection points, do both.

## 1. Cookie + init script (before navigation)

Shopee stores its computed device fingerprint in the cookie `shopee_webUnique_ccd`
(format: `p1|p2|p3|08|<platform>`, url-encoded → `%7C` for `|`). Set it before `goto`
so the signup SDK reads a known value:

**Exact segment shape (from real captures — guessing the lengths makes Shopee reject
it or flag the session):**
- `p1` = **base64(16 bytes)** → 24 chars, ends with `==`
- `p2` = **base64(64 bytes)** → 88 chars, ends with `=`
- `p3` = **base64(12 bytes)** → 16 chars, no padding
- platform suffix: **`|08|1` = Android, `|08|2` = iOS, `|08|3` = Windows**

Generate it deterministically per phone so the same number always yields the same
fingerprint (stability) while different numbers differ (uniqueness): seed an RNG with
`md5(phone + platform)`, draw that many random BYTES per segment, base64-encode, then
`urllib.parse.quote(raw, safe='')` so `|` and `+` become `%7C`/`%2B`.
**Do NOT build the segments from truncated md5-hex** — the char length and base64
padding come out wrong and no longer match the real shape.

```python
import urllib.parse as up
val = fp if "%" in fp else up.quote(fp, safe="")
context.add_cookies([{"name": "shopee_webUnique_ccd", "value": val,
                      "domain": ".shopee.co.id", "path": "/"}])
page.add_init_script(
    "try{document.cookie='shopee_webUnique_ccd=%s; path=/; domain=.shopee.co.id';}catch(e){}" % val)
```

- URL-quote the value first; the `|` separators must survive cookie encoding.
- Do this on the CONTEXT (cookie domain `.shopee.co.id`) plus an init script so a
  later navigation or SPA reset re-applies it.

## 2. API payload echo (direct-API fallback)

When falling back to a direct signup-by-OTP API call, the payload must carry the
same fingerprint:

```python
payload = {
  "otp_token": otp_token,
  "password": hashed,          # sha256(md5(password)) on Shopee
  "stay_logged_in": True,
  "client_identifier": {"security_device_fingerprint": fp},
}
# POST /api/v4/account/signup_by_otp with x-api-source: pc, x-requested-with: XMLHttpRequest
```

- Password hash on the API path is `sha256(md5(pw))`, NOT the raw form value — the
  browser form hashes differently, so a direct-API password and a form password are
  NOT interchangeable for the same account.
- A fingerprint mismatch between cookie and payload is a common silent auth failure:
  the account is created but `error:19` on the first authenticated call.

## Why it matters

A farm that omits the fingerprint still often *creates* the account, but the session
is flagged and downstream authenticated endpoints return `error:19`. If accounts
reproducibly create yet never authenticate, check that the SAME fingerprint is present
in both the cookie jar and the API payload before chasing the cookie-extraction path.
