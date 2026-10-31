---
name: shopee-captcha-solver
description: Solve Shopee captcha via SadCaptcha API (3 types).
---

# Shopee Captcha Solver (SadCaptcha) — 3 Tipe Challenge

## Trigger
Use when solving Shopee Indonesia captcha (signup/login) via SadCaptcha API, or building a Shopee auto-register/farm bot. Covers the 3 challenge types, exact selectors, drag mechanics, and the trusted-input requirement.

## Ringkasan

Shopee captcha punya **3 tipe**, masing-masing butuh endpoint + mekanik drag BERBEDA. Salah pilih tipe = API balikin angka tapi drag selalu gagal (captcha refresh terus).

| Tipe | Muncul kapan | Endpoint SadCaptcha | Mekanik |
|---|---|---|---|
| **PUZZLE** (puzzle slide) | signup, kadang login | `/puzzle` | drag GRIP horizontal, `dist = puzzle_width × prop` |
| **IMAGE_CRAWL** (arced slide) | **signup & login Shopee ID (paling umum!)** | `/shopee-image-crawl-pre-analyze` lalu `/shopee-image-crawl` | sweep trajectory diagonal → drag |
| **IMAGE_DRAG** (drag piece + Verify) | jarang (canvas puzzle + img piece) | `/shopee-image-drag` | drag PIECE (elemen img) ke titik → klik VERIFY |

**Cara identifikasi:** cek selector mana yang ada di DOM. **Gunakan URUTAN INI — kalau salah, drag gagal terus.** Untuk Shopee ID signup, tipe yang muncul TERBUKTI = IMAGE_CRAWL (selector `aside canvas[draggable=true]`). Cek: IC_PIECE dulu → PZ_PIECE → ID_PUZZLE.

## Selector (dari chrome-ext resmi, TERBARU)

**PENTING: versi TERBARU** (lihat `references/official-sadcaptcha-source.md`):
```js
IMAGE_CRAWL_PUZZLE_IMAGE = "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false], div:not(#puzzleContainer) > img"
IMAGE_CRAWL_PIECE_IMAGE  = "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"
IMAGE_CRAWL_BUTTON       = "#sliderContainer > div > div"
IMAGE_CRAWL_UNIQUE       = ["#NEW_CAPTCHA", "#captchaMask"]
```
SDK versi lama: puzzle=".DfwepB", pieceContainer="#puzzleContainer", piece="#puzzleImgComponent".

```js
// IMAGE_CRAWL
IMAGE_CRAWL_PUZZLE = "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false], div:not(#puzzleContainer) > img"
IMAGE_CRAWL_PIECE  = "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"
IMAGE_CRAWL_BUTTON = "div:has(> svg + svg)"
IMAGE_CRAWL_RESET  = "#NEW_CAPTCHA svg[viewBox='0 0 16 16'], aside svg[viewBox='0 0 16 16']"
IMAGE_CRAWL_UNIQUE = [IMAGE_CRAWL_PIECE]

// PUZZLE
PUZZLE_BUTTON = 'aside[aria-modal=true] div[style="width: 40px; height: 40px; transform: translateX(0px);"]'
PUZZLE_PUZZLE = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=false]"
PUZZLE_PIECE  = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=true]"
PUZZLE_UNIQUE = [PUZZLE_PIECE]

// IMAGE_DRAG
IMAGE_DRAG_VERIFY = ".rb6XLo, #NEW_CAPTCHA button:not(:has(*)), aside button:not(:has(*))"
IMAGE_DRAG_PUZZLE = "#NEW_CAPTCHA canvas, aside canvas"
IMAGE_DRAG_PIECE  = "#NEW_CAPTCHA img, aside img"
IMAGE_DRAG_UNIQUE = [IMAGE_DRAG_PUZZLE, IMAGE_DRAG_VERIFY]

CAPTCHA_PRESENCE = [PUZZLE_BUTTON, "#NEW_CAPTCHA", "#captchaMask", IMAGE_CRAWL_PIECE, IMAGE_DRAG_PUZZLE, IMAGE_CRAWL_RESET]
```

**Catatan Shopee ID:** puzzle bisa `<canvas>` (EkGpDI) atau `<img>`; piece image-drag = `<img>` (bukan canvas). Selalu extract dgn `elementToDataUrl()`: canvas → `.toDataURL()`, img → `.src`.

## Mekanik per tipe (replika PERSIS dari ext resmi)

### PUZZLE (simple slide)
```python
button_bbox = box(PUZZLE_BUTTON); sx, sy = center(button_bbox)
mouse.move(sx, sy); mouse.down()
for px in range(10):  # prep-drag buka papan
    mouse.move(sx + 10, sy + math.log(1 + px)); sleep(0.02)
puzzle_b64 = elementToDataUrl(PUZZLE_PUZZLE)
piece_b64  = elementToDataUrl(PUZZLE_PIECE)
prop = POST /puzzle {puzzleImageB64, pieceImageB64} -> slideXProportion
slide_bar_width = width(PUZZLE_PUZZLE)   # = lebar image, BUKAN elemen bar
dist = int(prop * slide_bar_width)
for px in range(10, dist):
    mouse.move(sx + px, sy + math.log(1 + px)); sleep(0.01)
mouse.move(sx + dist, sy); sleep(0.134)
mouse.up()
```
**PENTING:** `slide_bar_width = lebar IMAGE puzzle` (komentar resmi: "The slide bar is always the same as the image. We do not get the width of the bar element itself, because the css selector varies from region to region."). JANGAN pakai `track_w − grip_w`.

### IMAGE_DRAG (drag piece + Verify) — paling sering di SIGNUP Shopee ID
```python
piece_ele  = waitFor(IMAGE_DRAG_PIECE)      # <img>
puzzle_ele = waitFor(IMAGE_DRAG_PUZZLE)     # <canvas>
puzzle_b64 = elementToDataUrl(puzzle_ele)
piece_b64  = elementToDataUrl(piece_ele)
start = center(piece_ele)
mouseApproach(start.x, start.y)             # cubic bezier natural approach
resp = POST /shopee-image-drag {puzzleImageB64, pieceImageB64} -> {proportionalPoints:[{proportionX,proportionY}]}
bbox = viewportRect(puzzle_ele)
answerX = bbox.x + resp.proportionalPoints[0].proportionX * bbox.width
answerY = bbox.y + resp.proportionalPoints[0].proportionY * bbox.height
mouse.down(start.x, start.y)
for pt in generateNaturalApproach(start, {answerX, answerY}, 20):  # bezier 20 titik
    mouse.move(pt.x, pt.y); sleep(0.01 + rand*0.02)
mouse.up(answerX, answerY)
sleep(0.15)
clickElement(IMAGE_DRAG_VERIFY)             # KLIK TOMBOL VERIFY
sleep(5)
```
**KUNCI:** drag **ELEMEN PIECE** (bukan grip), ke koordinat `prop × bbox`, lalu **KLIK VERIFY**. Respons `MultiPointResponse` = array titik (pakai `[0]`).

### IMAGE_CRAWL (arced slide) — LOGIN
```python
# 1. refresh dulu (klik reset, tunggu gambar ganti)
# 2. pre-analyze: POST /shopee-image-crawl-pre-analyze {image_b64: puzzle} -> {version, slideXProportion, skipRecommended}
#    skip kalau skipRecommended=True atau slideXProportion>=0.99 (max SKIP_CAP=3)
# 3. mouse down di slide button, sweep trajectory diagonal:
#    mouse.move(btnX + pixel, btnY - pixel)  # -pixel = diagonal!
#    tiap pixel rekam: {pixels_from_slider_origin:pixel, piece_rotation_angle, piece_center:{proportionX,proportionY}}
#    piece_center = proportional dlm puzzle bbox (round 4 desimal)
#    scatter blok 30px (acak urutan), step 3px, stop kalau piece gak gerak / lewat maxProp
#    sort trajectory by pixels_from_slider_origin; minimal 12 baris
# 4. POST /shopee-image-crawl {puzzle_image_b64, piece_image_b64, slide_piece_trajectory:[...]} -> {pixelsFromSliderOrigin}
# 5. drag gesture swing: osilasi (GESTURE_AMP_U=1.5, GESTURE_PASSES=4) lalu leg ke solution
#    maxPx = puzzle_width * 0.85; toU(px)=px/maxPx*4-2; toPx(u)=(u+2)/4*maxPx
#    leg(at, toPx(u), 13) tiap pass; leg(at, solution, 15) terakhir
#    releasePx = toPx(round((toU(solution)+0.02)*1e4)/1e4)
#    pause 900-2100ms, move ke releasePx, pause 750-1450ms, mouse.up
```

## TRUSTED INPUT (WAJIB — kalau nggak, drag nggak regis)

Shopee ignore mouse sintetik biasa. Ext resmi pakai **`chrome.debugger` → CDP `Input.dispatchMouseEvent`** (trusted).

**Di Playwright, `page.mouse.*` SUDAH = CDP `Input.dispatchMouseEvent` (trusted).** Cukup `page.mouse.move/down/up`. JANGAN dispatch `MouseEvent`/`PointerEvent` sintetik via `page.evaluate()` — itu transparet & dideteksi (kecuali sbg fallback).

Kalau butuh batch antar frame (crawl): CDP `Input.dispatchMouseEvent` berturut-turut dengan `timestamp` incremental (spacing 0.002s).

## API SadCaptcha (base `https://www.sadcaptcha.com/api/v1`)

| Endpoint | Req | Resp |
|---|---|---|
| `GET /license/credits?licenseKey=` | — | `{credits}` |
| `POST /puzzle?licenseKey=` | `{puzzleImageB64, pieceImageB64}` | `{slideXProportion}` |
| `POST /shopee-image-drag?licenseKey=` | `{puzzleImageB64, pieceImageB64}` | `{proportionalPoints:[{proportionX,proportionY}]}` |
| `POST /shopee-image-crawl-pre-analyze?licenseKey=` | `{image_b64}` | `{version, slideXProportion, skipRecommended}` |
| `POST /shopee-image-crawl?licenseKey=` | `{puzzle_image_b64, piece_image_b64, slide_piece_trajectory:[{pixels_from_slider_origin, piece_rotation_angle, piece_center:{proportionX,proportionY}}]}` | `{pixelsFromSliderOrigin}` |

- Auth: `?licenseKey=<KEY>` di query.
- HTTP 400 = bad request / jawaban nggak ketemu. HTTP 401 = key salah / kredit habis.
- Harga ~$0.0020/solve. 25 kredit gratis saat daftar.
- **Hemat kredit:** hash puzzle image → cache jawaban per-hash (puzzle sama = skip API call).

## Prasyarat environment
- Playwright chromium terinstall (`playwright install`).
- Proxy Indonesia WAJIB (Shopee ID geo-gate). Format vsproxy: `http://user:pass@host:port`.
- Injeksi cookie `shopee_webLanguage=id` (domain `.shopee.co.id`) sebelum goto — hilangin modal bahasa.
- Dismiss modal "Pilih bahasa Anda" (klik "Bahasa Indonesia") — modal bisa respawn, loop sampai bener-bener hilang.
- Chain signup: lang modal → form (1 field) → TOS "Simak Ketentuan Akun" Setuju → captcha → `get_settings_v2` → `send_otp` → OTP.
- Modal OTP: pilih channel via "Metode Lain" (WhatsApp default / SMS), lalu klik "Kirim ke WhatsApp"/"Kirim Kode".

## ENH-A — lessons dari integrasi resmi (2026-10-16, TERBUKTI jadi akun)

Diintegrasikan ke `shopee_hold.solve_image_crawl` (flow utama yg sudah jalan). **JANGAN rebuild** — tambahkan ke pipeline yg ada.

1. **Sweep harus DIAGONAL**: `mouse.move(btnX + px, btnY - px)` (bukan lurus `±random`). Kalau lurus, piece sering tak bergerak → trajectory flat → **API `image-crawl` balas HTTP 400**.
2. **Grip versi baru TIDAK punya `#sliderContainer`**. Kalau `count=0`, fallback JS: cari elemen `34-60px` di bawah puzzle (`rect.top > puzzleBottom`, ambil x terkecil). Terbukti: `div.dExCsf.LBTCqK.GkWZlf` (40x40).
3. **GUARD piece bergerak** (wajib): saat sweep, track `piece_center.proportionX`; kalau tidak berubah ≥12 step → berhenti & retry. Cek `max-min < 0.02` → drag gagal → jangan kirim ke API (buang kredit) → retry puzzle.
4. **EARLY-STOP** di `piece_center.proportionX >= slideXProportion` (+overshoot 15px) — hemat waktu & kredit.
5. **GESTURE SWING release** (bukan drag lurus): `maxPx=puzzleW*0.85; toU(px)=px/maxPx*4-2; toPx(u)=(u+2)/4*maxPx`; 4 pass osilasi `a=1.5*(1-c/4)` selang-seling, lalu leg ke solution, lalu nudge `+1..3px`, pause 0.9-2.1s, release, pause 0.75-1.45s, mouse.up.
6. **Cache tetap dipakai** (proporsional) — `prop = target/bar_w`, lookup sebelum panggil API.

Hasil: `6285602739981` → user `16596801848`, WA OTP, cookie valid, `phone_verified:true` (API `error:0`). Nomor sebelumnya gagal 6x (trajectory 400) sebelum guard+A fix.

## ENH-D — interstitial & pre-check (2026-10-16)

- **ENH-D1** — interstitial pasca-OTP ada **2 bentuk**:
  1. `Apakah ini akunmu?` → klik `Buka, buat akun baru`.
  2. **MODAL `Diperlukan Identifikasi Tambahan`** (BARU): `Untuk membuat akun dengan no. handphone ini, CS Shopee membutuhkan informasi kontakmu...` tombol **[Batal] [Ya, Lanjutkan]**. Klik **`Ya, Lanjutkan`** (oranye) → paksa lanjut buat akun. Kalau ga ditangani → state `?` → CLOSED.
  Deteksi via 5x loop sampai state maju (bukan sekali).
- **Pre-check nomor (fresh/terdaftar)**: `POST otp/get_settings_v2 {operation:8}` **TIDAK** membedakan fresh vs terdaftar utk nomor ID (`available_channels:[3,2,1]` di dua-duanya). Diskriminator sejati = **`GET /api/v4/account/basic/check_phone_exist?otp_token=<dari send_vcode>`** → muncul `Apakah ini akunmu?`/modal bila terdaftar. Butuh OTP round-trip (tak ada pre-check gratis). `phone_checker.py` = implementasi (API + DOM interstitial).
- **`endpoint`**: `check_phone_exist` GET, `otp_token` = `%`-encoded beraρ dari response `send_vcode`.

## Modul ops (Tier 5-12, 2026-10-16)

- **#5 `account_warmer.py`** — ping `get_account_info` + warm (home + subcart) → `accounts_health.json`. Cron 6h `--proxy --warm`.
- **#6 `stats.py`** — agregasi akun/cache/proxy/key/limit. `summary()` + `text_block()`. Dipakai dashboard bot.
- **#7 `proxy_health.py`** — test geo ID (ip-api) + latency → skor → `proxies_best.txt`/`proxy_health.json`. Cron 2h. (ip-api via proxy lambat ~7-12s, normal.)
- **#8 cron** — prewarm cache 20m, warmer 6h, proxy 2h, watchdog 30m (`cron_shopee.txt`).
- **#9 `otp_policy.py`** — `auto_resend()`: baca `remaining_resend_cooldown_sec` → tunggu → `send_vcode` ch3→1→2 backoff. `23500101`=butuh captcha, `23500152`=rate-limit.
- **#10 `worker_pool.py`** — N worker paralel (`shopee_hold` per nomor+proxy+key). OTP file per-nomor `.otp_input_<phone>`.
- **#11/#12** — riset: sz-sdk WASM (x-sap-*) & solver lokal. Belum shipped (lihat catatan).
- **Bot fitur baru**: tombol `🔍 Checker Nomor` (checkmenu) + dashboard diperkaya stats.py.

## Modul pendukung (shopee-farm) — Tier1/2 dev

- **`fpgen.py`** (#11) — fingerprint `shopee_webUnique_ccd` (format `p1%7Cp2%7Cp3%7C08%7C1`) **deterministik per nomor** + device profile (12 device ID nyata, UA konsisten). Auto-dipakai `shopee_hold` kalau tak ada `--fp`.
- **`health_monitor.py`** (#9) — cek akun berkala via `account_info`; ALIVE/DEAD/ERR → `accounts_health.json`. `error=19` = cookie tak lengkap (SPC_ST hilang) = akun dibuat sebelum ENH#8.
- **`prewarm_cache.py`** (#5) — harvest puzzle offline (buka captcha → reset → hash → cache) tanpa daftar. Cache-hit = 0 kredit.
- **`key_watchdog.py`** (#6/#7) — feed key dari `/root/sadfarm/accounts.json`+`keypool.json` → `sadkey_db.add_key`; jaga pool (min-alive/min-credits) → auto-harvest; tulis `bot_key.txt`. Cron: */30.
- **`pure_signup.py`** (#12) — `signup_by_otp` via **page-context fetch** (sz-sdk sign otomatis in-page) = API-semantik tanpa reverse WASM. `_hash_pw` = sha256(md5(pw)). Fallback ENH-C1 di `shopee_hold`.
- **ENH-B1** anti `no img` (tunggu render ≤20s); **ENH-B2** auth-cookie hardening (45s + re-nav home tiap 10s); **ENH-B3** auto fingerprint.
## Anti-fraud: `x-sap-ri`/`x-sap-sec`/`af-ac-enc-sz-token` digenerate sz-sdk 1.12.45 (JS+WASM) per-request.

**UPDATE 2026-10-16 — full reverse map + stop-line:** lihat skill
`security/shopee-antifraud-reversing`. Ringkas:
- **Solved:** Sense SDK AES-128-CBC (`SenseTestKey1234`/`SenseTestIV12345`),
  CRC variant (`75 ab 5a <crc32&0xFF>`), x-sap-ri layout
  (`[ts LE][nonce][counter][marker 0x1201][sig19]`), sz-token struktur
  (`b64(16)|b64(64 SIG)|b64(12)|08|plat`), + 2592 string decoded.
- **STOP-LINE:** signer `x-sap-sec` (19-byte) + kunci `af-ac` ada di dalam
  **bytecode VM (~443 opcode, binary-search dispatch)** — `vmp_*` prefix, no WASM,
  WebCrypto kosong. Reversal penuh multi-hari. Tanda VM terdeteksi, berhenti.
- **Jalan pintas (terbukti):** page-context `fetch()` di halaman live → SDK tanda
  tangan otomatis. `pure_signup.py` / ENH-C1 fallback.

## Pitfalls yang sudah terbukti

1. **Salah endpoint.** `/puzzle` balikin angka tapi kalau tipenya image-drag/image-crawl, drag bakal gagal terus. Identifikasi tipe DULU.
2. **Pakai synth event, bukan trusted.** Dispatch `PointerEvent` via JS gagal regis. Pakai `page.mouse`.
3. **`slide_bar_width` salah.** Harus = lebar IMAGE puzzle, bukan lebar elemen bar, bukan `track_w − grip_w`.
4. **Image-drag: drag grip, bukan piece.** Harus drag ELEMEN PIECE ke koordinat, lalu klik Verify.
5. **Lupa tunggu "Memuat..." hilang.** Extract canvas sebelum siap = gambar kosong → prop ngawur.
6. **Rate limit ~5-6 attempt/nomor** → "Verifikasi gagal. Silakan coba lagi beberapa menit lagi." Nomor habis = stuck di modal bahasa.
7. **Sequential number rejected** — nomor berurutan mentah sering ditolak attempt 2+ (error 23500158).
8. **Kredit habis cepat** kalau debug tanpa cache — pakai cache hash + identifikasi tipe yg benar.

## LESSON — kripto captcha = RSA-1024 (BUKAN AES)

Reverse `bundle.a95de02.js` (799KB): payload captcha dienkripsi via fungsi `D(t)` pakai **RSA-1024 PKCS#1 v1.5**:
```js
U = "<256 hex>"   // modulus 1024-bit
S = "010001"      // public exponent 65537
new RSAKey().setPublic(U,S).encrypt(t)  // → base64
```
**Karena RSA publik → enkripsi BISA direplikasi tanpa secret server.** Modulus tersimpan: `/root/shopee-farm/rsa_modulus.txt`.

```python
N = int(open('rsa_modulus.txt').read().strip(), 16); E = 65537; K = (N.bit_length()+7)//8
def rsa_encrypt(data):
    ps = b'\xff'*(K-len(data)-3)
    em = b'\x00\x01'+ps+b'\x00'+data
    return base64.b64encode(pow(int.from_bytes(em,'big'),E,N).to_bytes(K,'big')).decode()
```

## PURE-API FLOW (tanpa browser, terbukti 2026-10-15)

`shopee_api.py` — `get_settings_v2` (plaintext) + `get_captcha_config` (plaintext) JALAN tanpa browser. Cuma geometry puzzle yang butuh browser (surface tertutup SDK).

```
1. POST /api/v4/otp/get_settings_v2          (plaintext) → need_captcha
2. POST /api/v4/anti_fraud/captcha/get_config (plaintext) → tracking_id
3. RSA-encrypt(payload) → POST /api/v4/anti_fraud/captcha/generate
4. [SOLVE geometry] ← butuh browser/SadCaptcha
5. RSA-encrypt(answer) → POST /captcha/verify
6. POST /api/v4/otp/send_otp {captcha_token}
```

Artefak: `shopee_api.py`, `rsa_modulus.txt`, `captures/session_*.json`, `API_REVERSE_RUNBOOK.md`, `CRYPTO_RSA_RESULTS.md`.

## ✅ PIPELINE FULL SIGNUP TERBUKTI JADI (2026-10-15)

Akun nyata terbuat: `+62 889 8623 6822` (pass `PASS_REDACTED`). Runner: `/root/shopee-farm/shopee_hold.py`.

### 6 BUG yang WAJIB difix (bandingkan dgn versi lama)

1. **Deteksi tipe dari SELECTOR**, bukan teks. Shopee ID tulis "Geser ... puzzle" TAPI tipe = image_crawl (`IC_PIECE`). Urutan: IC_PIECE→image_crawl, PZ_PIECE→puzzle, ID_*→image_drag.
2. **OTP = 6 kotak** — klik box pertama, ketik semua digit (auto-advance). Bukan single input.
3. **Klik LANJUT butuh fallback**: `page.keyboard.press('Enter')` + multi-selector. Selector doang sering gagal.
4. **Password validator**: Shopee WAJIB min 1 huruf BESAR + 1 kecil + 8-16 char. `PASS_REDACTED` ditolak → auto-kapital jadi `PASS_REDACTED`.
5. **KRITIS — klik DAFTAR: navbar bug.** Selector `daftar` match tombol "Daftar" di HEADER (y<120), bukan tombol submit form (y>600). Skip elemen `r.y < 120`, prioritas `r.width > 200`.
6. **Sesi harus DITAHAN** (hold) sampai akun konfirmasi — jangan close setelah submit.

### Mode holding (shopee_hold.py)
- Solve captcha → tulis `WAITING_OTP` ke `.signup_status` → tunggu kode di file `.otp_input` (poll max 5 menit).
- Setelah OTP benar → PASSWORD → fill `PASS_REDACTED` → klik DAFTAR → step 3 "Pendaftaran berhasil!".
- Env file: `.otp_input`, `.pw_input`, `.signup_status`.

### Rotasi proxy penting
Proxy vsproxy port 10000-10011 beda IP. Kalau captcha jadi **reCAPTCHA Google** (bukan slider Shopee) = nomor/IP ke-flag → ganti port proxy lain.

## Rekonsiliasi wallet (jika perlu)

## KENAPA PURE-API MUSTAHIL (temuan final 2026-10-15)

Bukan "AES obfuscated" biasa — Shopee pasang **3 lapis anti-bot**:

1. **AES key RANDOM per-request** (`bundle.js` ~295520): `i=nQ(16)` bikin AES key acak, lalu `a=Gt(i)=RSA-encrypt(i)`. Payload = AES-CBC(data, key yang cuma dikirim ter-RSA). Tanpa private key server → mustahil replika.
2. **SAP anti-fraud headers**: `af-ac-enc-sz-token` (dari sz-sdk native), `x-sap-ri` (52 hex sig), `x-sap-sec` (120 b64 sig). Di-generate sz-sdk (JS+WASM). Tanpa ini → 400.
3. **Geometry captcha** = surface tertutup SDK → wajib browser.

**Yang BISA API murni:** `get_settings_v2`, `get_captcha_config`, `captcha/feedback/questions`.
**Yang WAJIB browser:** `captcha/generate`, `captcha/verify_v2`, geometry.

## LESSON KRITIS — Chromium proxy auth (2026-10-15)
Chromium BUTUH proxy auth TERPISAH (`{server, username, password}`), BUKAN inline `http://user:pass@host`.
Inline gagal `407 NO_USER` kalau password ada karakter `;` (vsproxy `sessttl.5`).
Format benar: `launch(proxy={"server":"http://gb.vsproxy.org", "username":"<user>", "password":"[REDACTED]"})`.

## LESSON — Shopee SPA + Playwright flaky
- `page.goto(wait_until="load")` TIMEOUT di Shopee (resource ga pernah selesai) → pakai `"commit"` + poll selector.
- `page.click(sel)` bisa HANG di SPA saat navigasi → pakai mouse click via bounding box (`_mouse_click_text`).
- `page.evaluate("document.body.innerText")` HANG kalau page navigating → pakai `locator("body").inner_text(timeout=N)`.
- **Runner paling reliable tetap `shopee_hold.py`** (headless=False via xvfb, domcontentloaded) — terbukti jadi akun.

## Verifikasi
Screenshot akhir harus nunjukin modal "Kirim Kode OTP via WhatsApp" (sukses) — BUKAN puzzle lagi. Cek juga `verify calls` naik (Shopee terima request).

## LESSON KRITIS — deteksi tipe (2026-10-15, project /root/shopee-farm)
Shopee ID kadang render instruksi "Geser untuk menyelesaikan puzzle" PADAHAL tipping = IMAGE_CRAWL (canvas 44x44 draggable=true). Kalau tipe di-lock dari TEKS → POST ke `/puzzle` → API balikin angka → drag selalu gagal → buang attempt limit (5-6x/nomor).
**URUTAN DETEKSI WAJIB (dari selector, bukan teks):**
1. `IC_PIECE` (canvas[draggable=true] 44x44) → **image_crawl**
2. `PZ_PIECE` (img[draggable=true]) → **puzzle**
3. `ID_PUZZLE`/`ID_VERIFY` → **image_drag**
4. fallback terakhir: puzzle

## LESSON — kredit API
Skenario: semua endpoint OK, deteksi OK, tapi solve gagal diam2. Cek dulu: `GET /license/credits?licenseKey=KEY`. HTTP 401 = kredit habis / key salah. JANGAN debug deteksi kalau kredit 0.

## LESSON — infrastruktur /root/shopee-farm
- Solver: `shopee_v6.py` (3 tipe, patched 2026-10-15: selector-first detect + dry-run `--dry` mode + fallback grip detection)
- Bot Telegram: `shopeebot.py` — token `8046106656:AA...` (Owerte_bot), runtime `/root/sniffenv/bin/python`, xvfb-run wrapper, proxy rotasi dari `proxies_id_vs.txt` (vsproxy ID, 12 port)
- API key file: `bot_key.txt` (runtime, bisa /setkey via bot). Kredit cek: `curl https://www.sadcaptcha.com/api/v1/license/credits?licenseKey=KEY`
- Probe gratis: `probe_v6_dump.py` — nangkep canvas/img b64 TANPA panggil API, buat debug tipe captcha
- **Achicaptcha (docs.achicaptcha.com/id/docs/shopee-captcha) = provider alternatif, belum terkomp仄: web kadang diakses → kalau SadCaptcha mati, fallback ke sini
