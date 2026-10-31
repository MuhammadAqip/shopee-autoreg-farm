# PROJECT DEEP DIVE — Shopee Auto-Register Farm

Dokumentasi lengkap seluruh project: apa yang dibangun, bagaimana cara kerjanya,
apa yang terbukti, apa yang buntu, dan kenapa setiap keputusan diambil.

Ditulis tanpa narasi bisnis. Fakta teknis dan alasan teknis.

---

## Daftar Isi

1. [Masalah yang Dipecahkan](#1-masalah-yang-dipecahkan)
2. [Peta Lengkap Repo](#2-peta-lengkap-repo)
3. [Lapisan Sistem](#3-lapisan-sistem)
4. [Chain Signup Detail](#4-chain-signup-detail)
5. [Sistem Captcha](#5-sistem-captcha)
6. [Cache — Evolusi dan Angka](#6-cache--evolusi-dan-angka)
7. [Key Manager](#7-key-manager)
8. [Reputasi Nomor](#8-reputasi-nomor)
9. [Fingerprint & Device](#9-fingerprint--device)
10. [Reverse Engineering Anti-Fraud](#10-reverse-engineering-anti-fraud)
11. [Proxy & Jaringan](#11-proxy--jaringan)
12. [Panel & Observability](#12-panel--observability)
13. [Evolusi Keputusan](#13-evolusi-keputusan)
14. [Jalan Buntu Terdokumentasi](#14-jalan-buntu-terdokumentasi)
15. [Angka Produksi](#15-angka-produksi)
16. [Risk & Mitigasi](#16-risk--mitigasi)

---

## 1. Masalah yang Dipecahkan

Registrasi akun Shopee secara manual tidak bisa di-scale:

- Satu nomor = satu akun, butuh OTP
- Captcha muncul di hampir setiap percobaan
- Anti-fraud menandai IP dan device
- Cookie mati setelah 24 jam

Yang dibutuhkan: pipeline yang bisa **dijalankan berulang** tanpa operator
menunggu di depan layar, dengan biaya per akun yang terukur.

Tiga sumber biaya:

| Sumber | Biaya | Cara ditekan |
|---|---|---|
| Kredit captcha solver | per solve | cache + pre-check reputasi |
| Nomor HP | per nomor | reputasi prefix |
| Waktu | per akun | worker paralel + browser persisten |

Seluruh arsitektur dirancang untuk meminimalkan ketiganya.

---

## 2. Peta Lengkap Repo

```
project/                       329 file
│
├── ORKESTRASI
│   ├── farm_production.py          plan → run → classify → report
│   ├── worker_pool.py              worker paralel, proxy lock, rotasi key
│   ├── farm_browser.py             runner multi-akun
│   ├── farm_run.py                 runner alternatif
│   ├── auto_reg.py                 satu akun, debug
│   └── hybrid_official.py          bridging ke API resmi
│
├── CHAIN SATU AKUN
│   ├── shopee_hold.py              inti: fingerprint → captcha → OTP → akun
│   ├── aFac_handshake.py           handshake anti-fraud
│   ├── api_signup_test.py          tes chain via API
│   └── browser_captcha_wa.py       captcha via WA bridge
│
├── CAPTCHA
│   ├── captcha_cache.py            SQLite content-match
│   ├── captcha_resolve.py          resolver utama
│   ├── cache_cli.py                CLI cache
│   ├── cap_puzzle.py               ekstrak puzzle dari canvas
│   ├── capsave.py                  simpan puzzle
│   ├── capture_captcha_signup.py   capture flow captcha
│   └── sadcaptcha_client.py        client SadCaptcha
│
├── KEY & CREDIT
│   ├── key_manager.py              rotasi + failover + refresh
│   ├── key_watchdog.py             jaga min alive
│   └── key_store.py                penyimpanan key
│
├── REPUTASI
│   ├── phone_reputation.py         per nomor + per prefix
│   └── chart_stats.py              visualisasi
│
├── IDENTITAS
│   ├── fpgen.py                    fingerprint generator
│   ├── core/accounts.py            identitas Indonesia
│   ├── core/device.py              device spoof + IMEI Luhn
│   └── core/shopee_client.py       client endpoint
│
├── AKUN (PASCA-REGISTRASI)
│   ├── account_validator.py        cek cookie hidup
│   ├── account_warmer.py           panaskan akun
│   ├── account_login_repair.py     login ulang
│   └── backup_account.py           backup
│
├── REVERSE ENGINEERING
│   ├── vm_*.py (14 file)           VM SAP: dump, disasm, decompile, emulator
│   ├── ak_decode.py                decode string tables
│   ├── decode_all_tables.py        semua tabel
│   ├── sense_decrypt.py            Sense SDK crypto
│   ├── signer_oracle.py            oracle signing
│   ├── vm_signer_capture_final.py  capture signer live
│   └── capture_shpsec.py           capture shpsec
│
├── INFRA
│   ├── core/store.py               SQLite resumable
│   ├── bot_store.py                store untuk bot
│   ├── health_monitor.py           monitoring
│   ├── proxy_health.py             cek proxy
│   └── panel/app.py                panel web port 8088
│
├── TOOLS
│   ├── tools/captcha.py            solver adapter
│   ├── tools/proxy.py              proxy pool + OTP sink
│   ├── tools/signup_driver.py      driver chain JS-only
│   ├── tools/captcha_hook.py       hook fetch/XHR
│   ├── tools/captcha_flow.py       tunggu + crop
│   ├── tools/ui_solver.py          human_move/click/drag
│   ├── tools/slider_puzzle.py      analisis puzzle
│   ├── tools/gap_detect.py         deteksi celah v1
│   └── tools/gap_v2..v6.py         iterasi deteksi celah
│
└── RISET (50 file .md)
    ├── VM_100_PERCENT.md           status final VM
    ├── VM_JIT_BREAKTHROUGH.md      temuan JIT
    ├── CAPTCHA_CRYPTO_RESULTS.md   skema enkripsi
    ├── CRYPTO_RSA_RESULTS.md       RSA-1024
    ├── SADCAPTCHA_API_BREAKTHROUGH.md  endpoint fix
    ├── SOLVER_FINAL_STATUS.md      dinding surface tertutup
    ├── KESIMPULAN_PROJECT.md       ringkasan arsitektur
    ├── P1_P2_P3_SELESAI.md         produksi stabil
    └── ... 42 lainnya
```

---

## 3. Lapisan Sistem

### Lapisan 0 — Identitas

Dibuat sebelum browser dibuka.

```python
# core/accounts.py
def gen_identity():
    return {
        "name":     random_indonesian_name(),
        "email":    f"{random_token()}@{domain}",
        "password": strong_password(),
        "birth":    random_birthdate(18, 45),
    }

# core/device.py
def gen_device():
    return {
        "model":      random_android_model(),
        "android":    random_android_version(),
        "imei":       luhn_valid_imei(),      # 200/200 valid
        "spc_device_id": uuid4().hex,
        "fingerprint": f"{p1}|{p2}|{p3}|08|{platform}",
    }
```

**Invariant:** satu akun = satu device. Device dipakai ulang kalau akun
di-retry, tapi tidak pernah dipakai untuk akun lain.

### Lapisan 1 — Jaringan

```python
# tools/proxy.py
class ProxyPool:
    def acquire(account_id) -> proxy     # pin per akun
    def release(proxy)                   # lepas lock
    def health_check(proxy) -> bool
```

Proxy dipin **per akun**, bukan per request. Ganti IP di tengah chain =
`security_device_fingerprint` tidak cocok dengan IP sebelumnya = flag.

Wajib residential Indonesia. Datacenter IP ditolak.

### Lapisan 2 — Browser

Playwright Chromium, headless (atau xvfb kalau `HEADLESS=false`).

Yang dilakukan browser:

1. Render halaman signup
2. Jalankan bundle `browser-signals` → fingerprint asli
3. Hasilkan `security_device_fingerprint`
4. Pasang `_sap_hook_fetch` → tiap `fetch()` ditandatangani
5. Rekam trajectory captcha

Yang **tidak** dilakukan browser: menyelesaikan captcha. Itu API.

### Lapisan 3 — Captcha

```
puzzle muncul
  ↓
cache lookup (puzzle_b64)
  ├─ HIT  → jawaban langsung, 0 kredit
  └─ MISS → SadCaptcha API
              ├─ pre-analyze
              ├─ rekam trajectory (browser)
              ├─ solve (API)
              └─ simpan ke cache
```

### Lapisan 4 — Orkestrasi

```
farm_production.py
  ├─ plan N nomor (pre-check reputasi)
  ├─ worker_pool (concurrency 2)
  │    ├─ proxy lock
  │    ├─ key assignment
  │    └─ hold_account
  └─ classify + report + simpan
```

---

## 4. Chain Signup Detail

### Urutan UI

```
1. GET https://shopee.co.id/buyer/signup
2. Gate bahasa: "Pilih Bahasa Anda" → klik "Bahasa Indonesia"
3. Input nomor (input[type=tel])
4. Ceklis TOS
5. Klik "Berikutnya"
6. Modal "Simak Ketentuan Akun Shopee" → klik "Setuju"
```

### Request 1 — get_settings_v2

```
POST /api/v4/otp/get_settings_v2
```

Body:

```json
{
  "operation": 8,
  "phone": "6281234567890",
  "supported_channels": [1, 2, 3, 6, 0, 5],
  "client_identifier": {
    "security_device_fingerprint": "gq2qri+snOezkf56H6Mk6g==|dZ2s8nLw...|3gfOxLDWFjGqHOl0|08|3"
  }
}
```

Header wajib:

```
x-api-source:       pc        (desktop) | rweb (mobile web)
x-requested-with:   XMLHttpRequest
x-csrftoken:        <dari cookie csrftoken>
af-ac-enc-dat:      b0c9718544dc2712      (16 hex, per-request)
referer:            https://shopee.co.id/buyer/signup
```

Response:

```json
{
  "error": 0,
  "data": {
    "need_captcha": true,
    "captcha_scene": "signup",
    "available_channels": [3, 2, 1]
  }
}
```

### Request 2 — send_otp

```
POST /api/v4/otp/send_otp
```

Body menyertakan token captcha hasil solve:

```json
{
  "phone": "6281234567890",
  "operation": 8,
  "captcha_token": "<hasil solve>",
  "channel": 3
}
```

Response sukses → Shopee kirim OTP ke SMS/WA.

### Request 3 — verify

```
POST /api/v4/otp/verify_otp
```

```json
{
  "phone": "6281234567890",
  "otp": "123456",
  "operation": 8
}
```

Response sukses → cookie `SPC_U`, `SPC_ST` di-set.

### Request 4 — login_by_password (opsional)

```
POST /api/v4/account/login_by_password
```

```json
{
  "phone": "6281234567890",
  "password": "[REDACTED]",
  "support_ivs": true,
  "country_code": "ID"
}
```

| `error` | Arti |
|---|---|
| `0` | sukses |
| `2` | password salah |
| `89` | format ditolak (butuh shpsec) |
| `98` | password **benar**, perlu IVS |

### Bentuk `security_device_fingerprint`

```
gq2qri+snOezkf56H6Mk6g==|dZ2s8nLw...|3gfOxLDWFjGqHOl0|08|3
└──── base64 ───────────┘└─ base64 ─┘└── hex8 ───┘ op ver
```

Total 139 karakter. Dibentuk engine Tongdun dari:

- canvas hash
- WebGL renderer
- audio context
- font list
- timezone
- `hardwareConcurrency`
- sensor noise

**Tidak bisa dipalsukan dengan string buatan.** Requests polos ditolak.

---

## 5. Sistem Captcha

### Tiga jenis berbeda

| Konteks | Jenis | Penanganan |
|---|---|---|
| Signup desktop | reCAPTCHA v2 | `solve_recaptcha_v2(sitekey, url)` |
| OTP mobile | Slider geetest | `solve_geetest_slider(gt, challenge, url)` |
| anti_fraud | Image crawl | SadCaptcha `shopee-image-crawl` |

### SadCaptcha — protokol lengkap

```
base = https://www.sadcaptcha.com/api/v1
```

**Credits**

```
GET /license/credits?licenseKey=X
→ {"credits": 23}
```

**Pre-analyze**

```
POST /shopee-image-crawl-pre-analyze?licenseKey=X
body: {"image_b64": "<puzzle>"}
→ {"version": ..., "slideXProportion": 0.47, "skipRecommended": false}
```

Kalau `skipRecommended: true` atau `slideXProportion >= 0.99` → **refresh
captcha**, jangan coba solve. Kalau dipaksa solve, hasilnya pixely salah.

**Solve**

```
POST /shopee-image-crawl?licenseKey=X
body: {
  "puzzle_image_b64": "<puzzle>",
  "piece_image_b64":  "<piece>",
  "slide_piece_trajectory": [ ...minimal 12 baris... ]
}
→ {"pixelsFromSliderOrigin": 137}
```

**Kesalahan paling umum:** kirim body tanpa `slide_piece_trajectory` → `400`.

### Rekaman trajectory

```python
def record_trajectory(page, puzzle_w):
    traj = []
    mouse.down(piece_x, piece_y)

    x = 0
    step = 3
    block = []
    while x <= puzzle_w * 0.85:
        mouse.move(piece_x + x, piece_y)
        block.append(sample(x, rotation, piece_center))

        if len(block) >= 30 // step:          # tiap 30px
            random.shuffle(block)             # Fisher-Yates
            traj.extend(block)
            block = []

        # stop condition
        if piece_center.proportionX >= slide_x_prop + 15/puzzle_w:
            break
        if stalled >= 10:
            break
        x += step

    traj.sort(key=lambda r: r["pixels_from_slider_origin"])
    return traj
```

Format satu baris:

```json
{
  "pixels_from_slider_origin": 137,
  "piece_rotation_angle": 12.5,
  "piece_center": {"proportionX": 0.47, "proportionY": 0.62}
}
```

### Release manusiawi

Setelah dapat `target_px`, jangan langsung geser. Replikasi pola manusia:

```python
max_px = puzzle_w * 0.85
to_u = lambda px: px / max_px * 4 - 2
to_px = lambda u: (u + 2) / 4 * max_px

# 4 oscillation pass, amplitudo turun
for i in range(4):
    amp = 1.5 - i * 0.3
    for u in oscillate(target_u, amp):
        mouse.move(to_px(u), y)
        sleep(0.002)

# final leg
step = 15
while abs(cur - target) > step:
    cur += step if target > cur else -step
    mouse.move(cur, y)

sleep(rand(0.75, 1.45))     # pause sebelum release
mouse.up()
```

### Konstanta anti-bot

```
SCATTER_BLOCK_PX        = 30
GESTURE_AMP_U           = 1.5
GESTURE_PASSES          = 4
GESTURE_PACE_MS         = 2
SWING_SAFE_PX           = 12
OVERSHOOT_PX            = 15
PAUSE_BEFORE_NUDGE_MS   = [900, 2100]
PAUSE_BEFORE_RELEASE_MS = [750, 1450]
MIN_TRAJECTORY_ROWS     = 12
SKIP_CAP                = 3
PRESS_SETTLE_MS         = 150
SAMPLE_SETTLE_MS        = 20
```

Nilai ini direplikasi dari extension referensi. Mengubahnya tanpa kalibrasi
ulang akan membuat captcha ditolak.

### Selector DOM

```css
PUZZLE: #NEW_CAPTCHA canvas[draggable=false],
        aside canvas[draggable=false],
        div:not(#puzzleContainer) > img

PIECE:  #NEW_CAPTCHA canvas[draggable=true],
        aside canvas[draggable=true],
        #puzzleContainer > #puzzleImgComponent

BUTTON: div:has(> svg + svg)
```

---

## 6. Cache — Evolusi dan Angka

### Versi 1 (rusak)

```sql
PRIMARY KEY = sha256(puzzle_b64 + piece_b64)
```

Masalah: `piece_b64` berbeda tiap render walau puzzle sama. Hasilnya **selalu
MISS**.

### Versi 2 (benar)

```sql
CREATE TABLE cache (
  puzzle_b64 TEXT PRIMARY KEY,      -- content match
  answer_x   INTEGER NOT NULL,
  hits       INTEGER DEFAULT 0,
  verified   INTEGER DEFAULT 0,     -- hits >= 2
  created_at INTEGER
);
PRAGMA journal_mode = WAL;
```

Plus:

- fallback hash untuk entry lama (migrasi)
- `prune(max_age_days)` untuk hemat disk
- `verified` untuk menandai yang sudah terbukti

### Angka nyata

```
total puzzle tersimpan  : 161
puzzle pernah hit       : 21   (13%)
total hits              : 24
total misses            : 0
daftar setelah migrasi  : verified = 3
ukuran DB               : 24 MB  (~150 KB/puzzle)
```

**Interpretasi:** cache berfungsi (puzzle Shopee memang berulang), tapi hit
rate rendah karena rotasi. Cache = L1 penghemat, bukan tulang punggung.

### Perilaku yang benar

```
lookup(puzzle_b64)
  ├─ HIT verified  → pakai, kredit 0
  ├─ HIT unverified→ pakai, tandai (kalau salah, hits tidak naik)
  └─ MISS          → API solve → simpan
```

---

## 7. Key Manager

### Sumber key

```
sadkey_db       10 key
sadfarm/keypool  4 key
bot_key          1 key
─────────────────────────
gabungan        10 unique (ada overlap)
```

### API

```python
km = KeyManager.instance()

km.alive()          # list key dengan credit > 0
km.next()           # round-robin, prioritas credit tinggi
km.mark(key, n=1)   # kurangi credit
km.refresh()        # GET /license/credits untuk semua key
```

### Failover

```python
def api_post_fo(path, body, max_keys=3):
    for _ in range(max_keys):
        k = km.next()
        r = post(path, body, key=k)
        if r.status in (401, 403):
            km.mark_dead(k)
            continue
        if r.ok:
            km.mark(k)
            return r
    raise RuntimeError("semua key habis")
```

### Status saat ini

```
10 terdaftar · 6 alive · 118 kredit
```

### Watchdog

Cron `*/30` → `key_watchdog.py`:

```
alive < 2      → notif
credit < 20    → notif
alive == 0     → hentikan produksi
```

---

## 8. Reputasi Nomor

### Model

```python
{
  "phone": {
    "sukses": 0,
    "limit": 1,
    "last": 1793456000
  },
  "prefix": {
    "8787": {"total": 5, "limit": 5, "rate": 1.0},
    "8123": {"total": 8, "limit": 1, "rate": 0.125}
  }
}
```

### Aturan skip

```python
def check(phone):
    p = phones.get(phone, {})
    if p.get("sukses"):          return BLOCK("sudah sukses")
    if p.get("limit", 0) >= 2:   return BLOCK("limit 2x")

    pref = prefix_of(phone, 4)
    pr = prefixes.get(pref, {})
    if pr.get("total", 0) >= 3 and pr.get("rate", 0) >= 0.6:
        return BLOCK(f"prefix {pref} rate {pr['rate']:.0%}")

    return ALLOW
```

### Hasil verifikasi

```
prefix 8787 : limit 100% (5/5)  → semua nomor baru diblok ✅
prefix 8123 : limit 12.5% (1/8) → lolos
```

Kenapa penting: satu percobaan gagal = 1 kredit hangus + flag IP naik.
Mencegah sebelum jalan menghemat keduanya.

---

## 9. Fingerprint & Device

### Format token

```
p1|p2|p3|08|platform
```

| Bagian | Panjang | Isi |
|---|---|---|
| `p1` | 24 char base64 | hash canvas |
| `p2` | 24 char base64 | hash WebGL |
| `p3` | 16 char hex | hash audio |
| `08` | 2 char | operation |
| `platform` | 1 char | `1`=mobile, `2`=desktop |

Dibentuk runtime oleh bundle `browser-signals.js`. Tidak bisa disusun manual.

### Device spoof

```python
# core/device.py
def gen_device():
    model = random.choice(MODELS)              # 120+ model
    imei  = gen_luhn_imei()                    # 15 digit valid
    return {
        "model": model,
        "android": random_version(),
        "imei": imei,
        "spc_device_id": uuid4().hex,
    }
```

IMEI divalidasi Luhn — **200/200 lolos** dalam test.

### Kenapa device spoof tetap perlu

Server-side verification tidak hilang dengan spoof. Yang berubah:

- Device ID unik → tidak terdeteksi duplikat
- IMEI valid → tidak ditolak validasi format
- Model konsisten → fingerprint cocok

Yang **tidak** berubah: OTP tetap wajib, risk score tetap dihitung.

---

## 10. Reverse Engineering Anti-Fraud

### SAP VM

Bundle anti-fraud Shopee memakai VM untuk membangkitkan `x-sap-sec`.

Hasil reverse penuh:

```
Arsitektur  : JIT compiler + bytecode interpreter hybrid
Bytecode    : 70.943 slot
Encoding    : opcode = ac[pc-1]
              VERIFIED: HIT=40358, MISS=0
Disassembly : 25.378 boundary, 100% match vs trace
Interpreter : 14.420 karakter, dispatch tree 66 node, opcode maks 999
Memory      : base 6000, stride 16 (record), ~762 KB
Register    : slot 0..6000
Frame       : op732 alloc
JIT         : V() generate JS source (46 konstruksi) → y() = eval
```

Alur:

```
bytecode ──V()──► JS source ──eval──► fungsi hidup
                     ▲
                     │
              reflection table tE
              ("0x15" = "toString", "0x1a" = "__proto__", ...)
```

### String tables

```
ae (identifier) : 2.592 entry
  ae[3]  = "now"
  ae[12] = "slice"
  ae[14] = "var"
  ae[15] = "for"
  ae[16] = "throw"
  ae[17] = "catch"
  ae[18] = "default"
  ae[19] = "while"
  ae[20] = "return"

aj (strings) : 1.555 entry (primitif, vmp_*, endpoint)

tE (reflection) :
  "0x15" = "toString"
  "0x18" = "slice"
  "0x1a" = "__proto__"
  "0x1b" = "hardwareConcurrency"
  "0x1e" = "P|I"        (separator)
```

### JIT generated sources

800 source JS tertangkap dari flow:

```
- XOR string decoder : String.fromCharCode(a[c]^c)
- Fisher-Yates shuffle
- Array → CSV join
- Separator join (667)
```

### Header hasil signing

```
af-ac-enc-dat      : 16 hex = 8 byte uint64, per-request
                     7/7 request punya nilai unik
af-ac-enc-sz-token : sz-token terenkripsi
x-sap-ri           : 26 byte [ts][nonce][seq][marker 0x1201][sig 19B]
sz-token           : b64(16B) | b64(64B sig) | b64(12B) | 08 | plat
```

### Sense SDK

```
Algoritma : AES-128-CBC / PKCS7
CRC       : [magic 3B 75ab5a][crc32(body) & 0xFF][version BE]
Verifikasi: 28/28
```

### Kesimpulan praktis

Tiga pilihan produksi:

| Opsi | Cara | Kelebihan | Kekurangan |
|---|---|---|---|
| **A** (dipakai) | page-context fetch | SDK tanda tangan sendiri, tahan update | butuh browser |
| B | hook `y()` = eval | dapat source signer | rapuh ke update |
| C | emulator offline | tanpa browser | harus update manual tiap perubahan |

Opsi A dipilih karena **tahan update** — kalau Shopee ubah VM, browser tetap
menandatangani dengan benar tanpa kita ubah apa pun.

---

## 11. Proxy & Jaringan

### Wajib residential

```
datacenter IP  → ditolak / langsung flag
residential ID → lolos
```

Bukti: percobaan dengan datacenter IP selalu berakhir `limit` atau error
jaringan.

### Aturan pemakaian

| Aturan | Alasan |
|---|---|
| Pin per akun | ganti IP di tengah chain = token tidak cocok |
| 1 proxy = 1 worker | 2 akun, 1 IP bersamaan = flag |
| Rotasi antar akun | akun berbeda harus IP berbeda |
| Health check tiap 2 jam | proxy mati = akun gagal |

### OTP sink

```python
class ManualOTP:      # baca dari otp.txt (62812xxx:123456)
class HTTPOTP:        # adapter provider SMS-activation generik
class WAOTP:          # WA bridge
```

---

## 12. Panel & Observability

### Panel web

```
python3 panel/app.py      # http://localhost:8088
```

Zero dependency. Fitur:

```
daftar akun + status (ready/limit/failed)
export CSV / JSON
trigger run manual
lihat log terakhir
statistik per prefix
```

### Monitoring

```bash
python3 health_monitor.py       # overall health
python3 key_manager.py status   # kredit
python3 captcha_cache.py stats  # hit rate
python3 phone_reputation.py stats
python3 chart_stats.py          # grafik
```

---

## 13. Evolusi Keputusan

Tabel keputusan yang berubah karena data, bukan opini.

| Keputusan awal | Kenapa berubah | Keputusan akhir |
|---|---|---|
| Pure API tanpa browser | `security_device_fingerprint` tidak bisa dipalsukan | browser wajib |
| Cache hash `sha256(puzzle+piece)` | selalu MISS | content-match `puzzle_b64` |
| Retry pada "Identifikasi Tambahan" | kredit habis, IP makin flag | classify sebagai `limit`, skip |
| Solver OpenCV lokal | deteksi celah tidak stabil (25–56%) | SadCaptcha API |
| Emulator Android | SHPSSDK crash x86_64, arch mismatch ARM64 | browser desktop |
| Baca rect puzzle dari DOM | surface tertutup, semua hook gagal | kirim gambar ke API |
| Satu key SadCaptcha | jenuh di tengah produksi | rotasi 10 key + failover |
| Tanpa reputasi nomor | boros kredit di nomor pasti limit | pre-check per nomor & prefix |
| Trajectory palsu | pre-analyze menolak | rekam dari event mouse asli |

---

## 14. Jalan Buntu Terdokumentasi

Dicatat supaya tidak dicoba ulang.

### Puzzle captcha tidak bisa dibaca dari page

Semua jalur ekstraksi koordinat sudah dicoba:

```
DOM query              ❌  #anti_fraud_captcha = <div></div> kosong
iframe traversal       ❌  tidak ada iframe
shadow root            ❌  shadowHosts: []
getBoundingClientRect  ❌  MID RECTS: []
drawImage hook         ❌  cuma grip 44×44
WebGL texImage2D       ❌  tidak dipakai render puzzle
OffscreenCanvas        ❌  18 dipakai, tapi untuk fingerprint
```

Puzzle dirender di **surface tertutup SDK** — kemungkinan browser compositor
layer. Tidak ada jalur standar JS untuk membaca geometri atau gambarnya.

**Yang tetap terbukti:** drag → `/anti_fraud/captcha/verify` terpanggil, SDK
encrypt sendiri. Mekanisme solver 100% jalan, hanya sumber koordinat yang
jadi dinding.

**Solusi yang dipakai:** kirim `puzzle_b64` + `piece_b64` ke SadCaptcha. API
itu yang menganalisis gambar, bukan kita membaca rect.

### Emulator Android

```
x86_64  → SHPSSDK native crash saat startup
ARM64   → arch mismatch di emulator KVM
```

Aplikasi Shopee mendeteksi emulator. Jalur ini buntu.

### Alur yang berhasil

```
browser desktop + cookie + captcha API  ✅
```

---

## 15. Angka Produksi

```
Cache        : 161 puzzle, 21 hit (13%), 24 MB
Key          : 10 terdaftar, 6 alive, 118 kredit
Identitas    : IMEI Luhn 200/200 valid
Worker       : 8 nomor → 6 key berbeda (rotasi OK)
Klasifikasi  : 5/5 test pass
Proxy lock   : terverifikasi
Failover     : 401 → key berikutnya OK
```

### Biaya per akun (estimasi)

| Item | Biaya |
|---|---|
| Captcha | 0 (cache hit) atau 1 kredit (miss) |
| Nomor | 1 nomor per akun |
| Proxy | dibagi antar akun |
| Waktu | ~2–5 menit per akun |

Dengan hit rate 13%, rata-rata ~0.87 kredit per akun.

---

## 16. Risk & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Shopee update anti-fraud | token berubah | page-context fetch tahan update |
| Captcha rotate | hit rate turun | cache L1 + API L2 + prewarm |
| Kredit solver habis | produksi stop | multi-key + failover + watchdog |
| Nomor kena limit | gagal per nomor | pre-check reputasi |
| Proxy mati | akun gagal | health check tiap 2 jam |
| RAM habis | browser crash | `MAX_CONCURRENCY` ≤ 4 |
| Device duplikat | flag | satu akun satu device |
| IP sama dua worker | flag | proxy lock |

---

**Sumber angka:** semua hasil yang tercatat di 50 file `.md` di `project/`,
diverifikasi lewat skrip di repo ini.
