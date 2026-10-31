# Shopee signup — full chain + pure-API vs browser split

Two things worth knowing up front for Shopee signup: the STEP SEQUENCE (where the
post-captcha gates are), and which layers are replayable via direct HTTP.

## Full signup chain (state order)

```
lang-modal → fill phone → submit "BERIKUTNYA"
  → TOS "Simak Ketentuan Akun" → click "Setuju"
  → CAPTCHA  (solve; see captcha-solver-api-integration SKILL.md)
  → OTP modal  ("Kode OTP telah dikirim via WhatsApp ke (+62) ...")
  → PASSWORD step  ("Atur Password Kamu" / "Buat password")
  → SUCCESS  ("Selesai")
```

## State-detection regexes (test LAST stage first)

Check OTP/password headings BEFORE generic captcha text — a cleared captcha still
contains the captcha instruction string and will misread as `?` if matched first.

```
OTP       : Masukkan Kode OTP | Kode OTP telah dikirim | kirim ulang | Kode OTP Salah
PASSWORD  : Buat password | Penuhi persyaratan sandi | cocokkan kata sandi
TOS       : Simak Ketentuan Akun
ERROR     : telah terjadi kesalahan | Coba Lagi
CAPTCHA   : Geser untuk | Verifikasi untuk | Memuat   ← match this LAST
```

## Post-OTP field rules

- **OTP field:** usually ONE hidden input, not six boxes. `keyboard.type(code)` first;
  fall back to per-box clicks (six inputs each < ~70px) only if single-type fails.
- **Password:** Shopee requires min 1 lowercase, **min 1 UPPERCASE**, 8-16 chars.
  An all-lowercase password fails client-side validation — DAFTAR stays disabled,
  no server error, state stays `PASSWORD`. Capitalize the first char and retry.

## Captcha solve that keeps the session (agent feeds async input)

Solver holds the browser through OTP:
- write state to a status file after each stage (`WAITING_OTP`, `OTP_WRONG`, `DONE_<state>`)
- at the OTP step: click "Kirim ke WhatsApp"/"Kirim Kode", write `WAITING_OTP`,
  poll an input file (`.otp_input`) up to a few minutes
- agent writes the code: `echo -n "<CODE>" > .otp_input`
- on wrong code: write `OTP_WRONG`, clear the field, poll again — never tear down
- password file (`.pw_input`) mirrors the same mechanism
- run `background=true notify_on_complete=true`; poll the status file separately

## What is plaintext (replayable without a browser)

These endpoints carry no client-side crypto — a plain `requests`/`curl` call with the
right cookies + device fingerprint works:

- `POST /api/v4/otp/get_settings_v2` — body has `phone`, `operation:8`,
  `client_identifier.security_device_fingerprint`. Returns `need_captcha`,
  `captcha_app_key`, `session_info.seed`.
- `POST /api/v4/anti_fraud/captcha/get_config` — body
  `{app_key:"User.PC", scene:"signup", platform:"pc", request_id, captcha_id:""}`.
  Returns `bundle_url`, `tracking_id` (server session handle).
- `POST /api/v4/anti_fraud/captcha/feedback/questions` — plaintext.

Fingerprint format seen: `<b64>|<b64>|<b64_short>|<int>|<int>`; reusable until flagged.
Trade-off: easy to replay, but the fingerprint is what Shopee rate/risk-scores, so
reusing one across many numbers is what trips the ~5-6 attempt limit.

## OTP channel: WhatsApp vs SMS is decided by `operation`, not by the send call

`get_settings_v2` returns different channels depending on `operation`:
- `operation:8` (SIGNUP scene) → `preferred_channel:3`, `available_channels:[3,2,1]`,
  `need_captcha:true`, `captcha_scene:"signup"`.
- `operation:7` (LOGIN with phone) → `preferred_channel:3`, `available_channels:[3,2,1]`,
  `hidden_available_channels:[2]`, `captcha_scene:"login"`, `captcha_app_key:"User.PC"`.
  Use this when the operator wants the code sent to an ALREADY-REGISTERED number/account
  rather than creating a new one; the same captcha→"Metode Lain"→WhatsApp→`send_vcode
  channel:3` flow then returns `error:0` + `delivery_channel:3` + `latest_sent_channel:3`.
- `operation:0` (generic) → SMS only (`available_channels:[1]`).

**`available_channels` is server-decided from `operation`, NOT from request body.** Fields
like `support_whats_app`, `platform`, `appversion`, `ext`, and an inflated
`supported_channels:[1,2,3]` are IGNORED — they never flip `[1]` → `[3,2,1]`. Do not
conclude "WA is app-only / server-gated" from an `operation:0` probe returning `[1]`;
the register (`op:8`) and login (`op:7`) flows both expose WA. If WA is requested and you
get `23500161` (channel unavailable) the operation is wrong; `23500101` means captcha
not solved.

Channel enum: `{1:"sms", 2:"voice_call", 3:"whatsapp"}`. So WA = channel **3** under
`operation:8`; SMS = channel 1 under `operation:0`. Requesting WA while sending with
`operation:0` returns `error:10002` ("channel unsupported") because op:0 only advertises
channel 1.

- **SMS (`op:0, ch:1`) needs NO captcha** — `send_vcode` returns `error:0` directly.
- **WA (`op:8, ch:3`) REQUIRES captcha** (`23500101` "captcha token required" if absent).

### Pure-API WA send is NOT possible with a bare riskToken (`12301022`)

The anti-fraud `riskToken` (`<b64>|<b64>|<b64>|08|3` from `/v2/shpsec/web/report` on
host `df.infra.sz.shopee.co.id`) is the right *shape* but is **rejected** by
`send_vcode(op:8, ch:3)` with `error:12301022`. That error means "riskToken present but
not captcha-verified": `m_token` must be the `security_data` returned by
`anti_fraud/captcha/verify_v2` AFTER a PASSING solve — a raw beacon riskToken is not
accepted. Consequence: the only working WA path is browser-solve-captcha → dialog
"Kirim ke WhatsApp" → click (exactly what the runner's `wa` mode does). Maximize API by
keeping `get_settings_v2`/`get_config` pure-API, but the challenge + verify stay browser.

**End-to-end WA path is PROVEN to produce a VALIDATED account** (register → WA OTP →
password → SUCCESS → cookie with `SPC_U` / `SPC_CLIENTID` / `SPC_ST` → authenticated
`account_info` returns the real `userid`). The `send_vcode(op:8, ch:3)` call is fired by
the page itself once the captcha clears and the dialog's "Kirim ke WhatsApp" is clicked
with a TRUSTED click — you do not replay it by hand; doing so with a raw riskToken is
what yields `12301022`.

**Channel selection is a modal, not a param.** The OTP step first shows a
"kirim kode OTP via …" dialog; to move OFF the default channel click "Metode Lain"
(Other method) then the target channel button. Clicking the target button directly when
the dialog is already on that channel is what the `wa` runner does (state `OTP_MODAL` →
`click_btn(r"kirim ke whatsapp|kirim kode|kirim otp")`). All of these clicks must be
TRUSTED (`page.mouse`), or the dialog no-ops.

**Verify a WA account by three signals together:** status file ends `ACCOUNT_SAVED
user_id=… valid=True`; log line `[AUTH] cookie auth LENGKAP (SPC_U/SPC_CLIENTID/SPC_ST)`;
and the per-account JSON record has a non-empty `user_id` + `validated:true`. A cookie
that lacks `SPC_U` reads back `error:19` — see `device-fingerprint-injection.md`.

## Capturing this SPA: Playwright CDP + HAR beats mitmproxy

For Shopee's SPA, an inline mitmproxy chain makes React fail to hydrate (blank page,
`body` length ~22) — the drag/captcha DOM never renders. Capture instead with
Playwright CDP (browser → proxy direct, SPA renders) and dump the whole session to a
HAR via `new_context(record_har_path=...)`. HAR yields the per-request anti-fraud
headers (`x-sap-ri`, `x-sap-sec` ~2888 chars, `x-sz-sdk-version`, `x-csrftoken`,
`af-ac-enc-sz-token`). Burp/Caido/ZAP are manual-replay tools, not headless-loop tools;
Charles / HTTP Toolkit / Wireshark are wrong tools for this. Capture rule: attach BOTH
`page.on('request')` (stash `post_data` + url) and `page.on('response')` (match the
request object, read `resp.text()[:2000]`) so request/response bodies pair up.

## What is encrypted (needs the bundle's keys)

- `POST /api/v4/anti_fraud/captcha/generate` — body `{encrypted_data: "U2FsdGVkX1..."}`.
  `U2FsdGVkX1` base64-decodes to `Salted__` + 8-byte salt + ciphertext = **CryptoJS AES**
  (OpenSSL KDF). Requires the passphrase from the bundle.
- `POST /api/v4/anti_fraud/captcha/verify_v2` — body `{security_data: "ByQBAAAA..."}`.
  `ByQBAAAA...` decodes to a binary TLV: magic `0x07` + version `0x0124` (LE) + varint
  fields, with the AES blob (`U2FsdGVkX1`) nested around offset 36. Endpoint is
  `verify_v2`, NOT `verify`.

AES detail: CryptoJS OpenSSL KDF = `EVP_BytesToKey(MD5, passphrase, salt, 32, 16)` →
AES-256-CBC. Passphrase is inside the bundle — not reversed as of writing.

## Do NOT inject a native/emulator SHPSSDK token to "enable" WA — it trips F13

When a pure-API WA attempt with `operation:7` fails, a tempting move is to harvest the
real `security_device_fingerprint` (SHPSSDK `getLongToken()`, e.g. via an emulator +
Frida) and inject it into `client_identifier`. This BACKFIRES: the server returns
`23500158` with message `"Gagal Log in (F13): ... perangkat lunak/keras yang tidak
resmi"` — a device-integrity rejection. Send an EMPTY
`security_device_fingerprint` instead; the empty-token request is what makes the server
expose `available_channels:[3,2,1]`. Corollary: reversing/extracting native SDK tokens
(emulator + Frida + `getLongToken`, `getSHPSECAllData`) is a dead end for the WA channel
and only adds a F13 risk — do not spend a session on it for this goal. (`23500158` also
appears as a per-number throttle; the F13 variant carries the `error_msg` text, the
throttle variant does not.)

## The RSA public-key lever

`bundle.a95de02.js` contains an RSA encrypt helper:
```js
U = "<256 hex chars>"   // 1024-bit modulus
S = "010001"            // public exponent 65537
new RSAKey().setPublic(U, S).encrypt(t)
```
Because it is a PUBLIC key, RSA encryption is replayable with no server secret:
```python
N = int(open('rsa_modulus.txt').read().strip(), 16); E = 65537; K = (N.bit_length()+7)//8
def rsa_pkcs1_encrypt(data: bytes) -> str:
    ps = b'\xff'*(K-len(data)-3)
    em = b'\x00\x01'+ps+b'\x00'+data
    return base64.b64encode(pow(int.from_bytes(em,'big'),E,N).to_bytes(K,'big')).decode()
```
RSA is used for signing/derivation — it does NOT decrypt the `encrypted_data`/
`security_data` fields (those are AES). It only lets you PRODUCE a valid RSA-encrypted
value where the page expects one.

## What ALWAYS needs a browser

The challenge geometry itself. The puzzle is rendered on a closed SDK surface — DOM
query, frame traversal, shadow root, `getBoundingClientRect` hooks, `drawImage` hooks,
WebGL `texImage2D`, and `OffscreenCanvas` hooks all fail to expose its rect/image. So
even with a full API replay, the drag step still needs either a real browser or a
solver API fed a screenshot-derived crop.

## Net position

~60% of the chain is pure-API. Full browserless signup requires reversing both the
AES passphrase and the TLV schema, and still cannot avoid a browser/vision step for the
puzzle. Prefer: API for the plumbing, browser (or solver API) only for the challenge.
A `page.on('request'/'response')` capture (bodies truncated to a few KB) is the fastest
way to enumerate the live endpoints and confirm this split per target.
