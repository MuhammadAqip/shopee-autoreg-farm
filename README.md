<!-- HERO -->
<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white" alt="python">
  <img src="https://img.shields.io/badge/playwright-1.x-2EAD33?logo=playwright&logoColor=white" alt="playwright">
  <img src="https://img.shields.io/badge/files-370-informational" alt="files">
  <img src="https://img.shields.io/badge/docs-88-success" alt="docs">
  <img src="https://img.shields.io/badge/dry_run-safe-yellow" alt="mode">
  <img src="https://img.shields.io/badge/captcha-cached-brightgreen" alt="captcha">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license">
  <img src="https://img.shields.io/badge/status-active-brightgreen" alt="status">
</p>

<p align="center"><a href="https://github.com/MuhammadAqip?tab=stars"><img src="https://img.shields.io/badge/⭐_Star_this_repo-%E2%98%85-FFD700?style=for-the-badge" alt="Star this repo"></a></p>

<p align="center">
  <img src="assets/demo.gif" alt="demo" width="100%">
</p>
<h3 align="center">Farm registrasi Shopee berbasis browser nyata — fingerprint, captcha cache, rotasi key.</h3>

<p align="center"><code>shopee-autoreg-farm</code></p>

| | |
|---|---|
| **Stack** | Python · Playwright · SadCaptcha |
| **Ukuran** | 370 file · 88 dokumen |
| **Isi** | auto_reg · farm_production · worker_pool · key_manager |
| **Docs** | [README](README.md) · [AGENTS](AGENTS.md) · [ROADMAP](docs/ROADMAP.md) |

<details>
<summary><b>Screenshot — output nyata</b></summary>


</details>

---

# SHOPEE AUTO-REGISTER FARM

> Auto-registrasi akun Shopee Indonesia berbasis browser nyata, dengan
> captcha solver API, cache puzzle, reputasi nomor, dan rotasi kredit
> multi-key. Dibangun dari reverse engineering penuh terhadap sistem
> anti-fraud Shopee (SAP VM, Sense SDK, sz-token).

**Status:** fondasi selesai & terverifikasi · **Terakhir diperbarui:** 31 Oktober 2026
**Package:** 329 file kode · 50 dokumen riset · 13 skill · 14 dokumen teknis

---

## Daftar Isi

1. [Apa Itu Project Ini](#1-apa-itu-project-ini)
2. [Kenapa Harus Browser, Bukan API](#2-kenapa-harus-browser-bukan-api)
3. [Arsitektur](#3-arsitektur)
4. [Alur Registrasi End-to-End](#4-alur-registrasi-end-to-end)
5. [Komponen Utama](#5-komponen-utama)
6. [Sistem Captcha](#6-sistem-captcha)
7. [Rotasi Kredit & Key Manager](#7-rotasi-kredit--key-manager)
8. [Reputasi Nomor](#8-reputasi-nomor)
9. [Hasil Reverse Engineering Anti-Fraud](#9-hasil-reverse-engineering-anti-fraud)
10. [Isi Package](#10-isi-package)
11. [Instalasi](#11-instalasi)
12. [Menjalankan](#12-menjalankan)
13. [Cron & Otomasi](#13-cron--otomasi)
14. [Hasil Terverifikasi](#14-hasil-terverifikasi)
15. [Dinding yang Ditemui](#15-dinding-yang-ditemui)
16. [Pelajaran](#16-pelajaran)
17. [Untuk AI Agent](#17-untuk-ai-agent)

---

## 1. Apa Itu Project Ini

Farm registrasi akun Shopee yang berjalan otomatis. Empat lapisan:

| Lapisan | Fungsi |
|---|---|
| **Browser nyata** | Render halaman, hasilkan fingerprint, tanda tangani request |
| **Captcha solver** | SadCaptcha API — pre-analyze + trajectory + solve |
| **Cache puzzle** | SQLite content-match — hemat kredit kalau puzzle berulang |
| **Orkestrasi** | Scheduler, rotasi key, reputasi nomor, worker pool |

Tujuannya bukan "bot yang jalan sekali". Tujuannya **pipeline yang tahan
dioperasikan**: tahu kapan harus berhenti, tahu nomor mana yang harus
dilewati, tahu key mana yang masih punya kredit.

### Angka dari produksi

```
Cache puzzle    : 161 puzzle tersimpan, 21 pernah dipakai ulang (13%)
Key manager     : 10 key terdaftar, 6 hidup, 118 kredit
Runner          : dry-run OK, chain signup sampai captcha terbukti live
Identitas       : generator nomor Indonesia, IMEI Luhn 200/200 valid
```

---

## 2. Kenapa Harus Browser, Bukan API

Ini bukan pilihan, ini konsekuensi arsitektur Shopee.

Setiap request ke endpoint signup membawa header yang **dibuat di dalam
halaman oleh JavaScript**:

```
af-ac-enc-dat      : b0c9718544dc2712        (16 hex, per-request)
af-ac-enc-sz-token : <sz-token terenkripsi>
x-sap-sec          : <VM output>
x-sap-ri           : <26 byte runtime integrity>
security_device_fingerprint : gq2qr...|dZ2s...|3gfOxLDWFjGqHOl0|08|3
```

`security_device_fingerprint` dibentuk oleh engine Tongdun dari:

- canvas fingerprint
- WebGL renderer string
- audio context fingerprint
- font list
- timezone + bahasa
- hardwareConcurrency
- sensor noise

**Requests polos ditolak server.** Sudah dibuktikan: semua percobaan
`requests` murni balik error, sementara browser nyata lolos.

### Yang tetap butuh browser

| Tahap | Browser | Bisa API? |
|---|---|---|
| Load page + fingerprint | ✅ wajib | ❌ |
| Signing (`x-sap-sec`, `af-ac-*`) | ✅ wajib | ❌ |
| Captcha: rekam trajectory | ✅ wajib | ❌ |
| Captcha: **solve** | ❌ | ✅ API |
| OTP verify | ✅ | ❌ |
| Cache puzzle | ❌ | lokal |

**Kesimpulan:** "Minimal-Browser, Max-API". Browser hanya untuk tiga hal yang
memang tidak bisa dipalsukan — render, signing, trajectory. Sisanya API.

---

## 3. Arsitektur

```
┌──────────────────────────────────────────────────────────────┐
│  farm_production.py  ── scheduler ── plan 50 akun/hari       │
│                        jarak 10–30 menit, jam 02:00–05:00    │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  worker_pool.py  ── worker paralel                           │
│    pre-check reputasi  → skip nomor bermasalah               │
│    proxy lock          → 1 proxy = 1 worker                  │
│    key rotasi          → tiap nomor key beda                 │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  shopee_hold.py  ── satu akun, satu chain penuh              │
│    fpgen        → identitas + device spoof                   │
│    browser      → Playwright, page-context fetch             │
│    captcha      → cache L1 → SadCaptcha API L2               │
│    OTP          → sink (manual/HTTP/WA bridge)               │
└───────────────────────────┬──────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   captcha_cache.db    key_manager.py     phone_reputation.py
   161 puzzle          10 key, 6 hidup    per-nomor + per-prefix
   content-match       round-robin        block prefix ≥60% limit
```

### File inti

| File | Peran |
|---|---|
| `farm_production.py` | Orkestrator harian: plan → run → classify → report |
| `worker_pool.py` | Worker paralel dengan proxy lock + reputasi + rotasi key |
| `shopee_hold.py` | Chain satu akun: fingerprint → browser → captcha → OTP |
| `farm_browser.py` | Runner multi-akun berbasis browser |
| `auto_reg.py` | Satu akun, mode debug, capture token |
| `captcha_cache.py` | SQLite content-match + WAL + prune |
| `key_manager.py` | Rotasi & failover kredit SadCaptcha |
| `phone_reputation.py` | Track sukses/limit per nomor & prefix |
| `fpgen.py` | Generator fingerprint (mobile/pc) |
| `account_warmer.py` | Panaskan akun baru (cron 6 jam) |
| `account_validator.py` | Cek cookie masih hidup |
| `account_login_repair.py` | Login ulang akun yang sesinya mati |
| `core/` | accounts, device, shopee_client, store |
| `tools/` | captcha, proxy, solver, gap detect (v1–v6) |
| `panel/app.py` | Panel web zero-dep, port 8088 |

---

## 4. Alur Registrasi End-to-End

```
 1. SCAN MARKET
      nomor random dari prefix sehat, jam ideal (02:00–05:00)

 2. PRE-CHECK REPUTASI
      nomor sudah sukses? → skip
      nomor limit 2×?     → skip
      prefix limit ≥60%?  → BLOCK

 3. FINGERPRINT
      fpgen → identitas Indonesia + device spoof
      spc_device_id unik per akun, IMEI Luhn valid

 4. PROXY
      residential ID, dipin per akun, TIDAK boleh ganti di tengah chain

 5. BROWSER
      Playwright → shopee.co.id/buyer/signup
      gate bahasa → "Bahasa Indonesia"
      isi nomor (type=tel) → ceklis TOS → "Berikutnya"
      modal "Simak Ketentuan" → "Setuju"

 6. OTP SETTINGS
      POST /api/v4/otp/get_settings_v2
        {operation:8, phone:62xxx,
         supported_channels:[1,2,3,6,0,5],
         client_identifier:{security_device_fingerprint:"<token>"}}
      ← {need_captcha:true, captcha_scene:"signup"}

 7. CAPTCHA
      CACHE dulu (content-match puzzle_b64)
      HIT  → langsung jawaban, 0 kredit
      MISS → pre-analyze → rekam trajectory → solve API
             → gerakan manusiawi → release

 8. OTP REQUEST
      POST /api/v4/otp/send_otp (dengan captcha token)

 9. OTP INPUT
      sink baca SMS/WA → inject 6 digit → verify

10. AKUN JADI
      username, password, nomor, user_id, fingerprint, device_id, cookie

11. SIMPAN
      SQLite resumable + cache puzzle + reputasi nomor

12. NOTIF
      🟢 sukses / 🟡 limit / 🔴 gagal

13. KIRIM
      via WA bridge atau export CSV/JSON dari panel
```

### Gate yang sering muncul

```
"Identifikasi Tambahan"
  → anti-fraud menandai nomor
  → ini LIMIT, bukan error
  → skip nomor, catat ke reputasi
  → JANGAN retry buta
```

Retry buta di gate ini = buang kredit + tambah flag ke IP.

---

## 5. Komponen Utama

### `shopee_hold.py` — chain satu akun

Fungsi utama:

```python
hold_account(phone, proxy=None, key="auto") -> dict
```

Mengembalikan klasifikasi:

| Hasil | Arti |
|---|---|
| `ready` | ada `user_id` + cookie → akun jadi |
| `limit` | "Identifikasi Tambahan" / sudah terdaftar |
| `failed` | error lain |

Poin penting: **page-context fetch**. Semua request dikirim dari dalam
halaman lewat `page.evaluate(fetch)`, sehingga SDK Shopee menandatangani
sendiri. Tidak perlu reimplementasi signer.

### `worker_pool.py` — paralel aman

Tiga pengaman:

1. **Pre-check reputasi** sebelum worker jalan
2. **Proxy lock** — satu proxy hanya boleh dipakai satu worker bersamaan
3. **Key rotasi** per nomor (hindari satu key jenuh)

Terverifikasi: 8 nomor → 6 key berbeda dipakai.

### `captcha_cache.py` — hemat kredit

Evolusi yang penting:

```
SEBELUM: primary key = sha256(puzzle + piece)
  → piece beda tiap render → SELALU MISS

SESUDAH: primary key = puzzle_b64 (canonical)
  → content match, piece diabaikan
  → fallback hash untuk entry lama
+ WAL mode (reader tidak diblok writer)
+ kolom verified (hits >= 2)
+ prune(max_age_days) untuk hemat disk
```

Migrasi 161 entry lama: 3 verified, 21 pernah hit.

**Hit rate ~13%.** Cache itu penghemat, bukan tulang punggung. Selalu ada
jalur API.

### `key_manager.py` — rotasi kredit

```
sumber key : sadkey_db(10) + sadfarm/keypool(4) + bot_key
alive()    : credit > 0
next()     : round-robin, prioritas kredit tinggi
mark()     : -1 kredit tiap solve sukses
refresh()  : GET /license/credits, update
```

`shopee_hold.py` pakai `key="auto"`. Kalau 401/403 → failover otomatis ke key
berikutnya (maks 3).

### `phone_reputation.py` — cegah LIMIT

```
per nomor   : sukses → ok, limit → turun
per prefix  : 4 digit pertama
BLOCK prefix kalau limit-rate ≥60% dengan ≥3 sampel
```

Terverifikasi: prefix `8787` limit 100% → semua nomor baru diblok.

### `fpgen.py` — fingerprint

Menghasilkan identitas lengkap:

```
nama, email, password, tanggal lahir
device model, Android version, IMEI (Luhn valid)
spc_device_id unik
fingerprint mobile: p1|p2|p3|08|<platform>
```

Format token yang harus cocok dengan SHOPEE:

```
gq2qri+snOezkf56H6Mk6g==|dZ2s8nLw...|3gfOxLDWFjGqHOl0|08|3
└── base64 ──┘|└ base64 ┘|└── hex8 ──┘|op|ver
```

Di-generate runtime oleh engine Tongdun. Browser menghasilkan otomatis.

### `panel/app.py` — panel web

Zero dependency, port 8088:

```
daftar akun + status
export CSV / JSON
trigger run manual
liat log terakhir
```

---

## 6. Sistem Captcha

### Tiga jenis captcha Shopee

| Konteks | Jenis | Solver |
|---|---|---|
| Signup desktop | reCAPTCHA v2 | `solve_recaptcha_v2(sitekey, url)` |
| OTP mobile | Slider geetest | `solve_geetest_slider(gt, challenge, url)` |
| Shopee anti_fraud | Image crawl | SadCaptcha `shopee-image-crawl` |

### SadCaptcha — endpoint resmi

```
base: https://www.sadcaptcha.com/api/v1
```

| Endpoint | Body | Return |
|---|---|---|
| `GET /license/credits?licenseKey=X` | — | `{"credits": N}` |
| `POST /shopee-image-crawl-pre-analyze` | `{image_b64}` | `{version, slideXProportion, skipRecommended}` |
| `POST /shopee-image-crawl` | `{puzzle_image_b64, piece_image_b64, slide_piece_trajectory[]}` | `{"pixelsFromSliderOrigin": N}` |

**Penyebab error 400 yang paling sering:** body `/shopee-image-crawl`
**wajib** ada `slide_piece_trajectory` minimal 12 baris. Kirim cuma
`puzzle + piece` → 400.

Catatan format:

- `licenseKey` = **query param**, bukan header
- body `image-crawl` = **snake_case**
- endpoint lain = **camelCase**

### Format trajectory

```json
{
  "pixels_from_slider_origin": 137,
  "piece_rotation_angle": 12.5,
  "piece_center": {"proportionX": 0.47, "proportionY": 0.62}
}
```

### Algoritma solve lengkap

```
1. refresh captcha
2. ambil puzzle canvas → b64
3. PRE-ANALYZE
     skipRecommended        → retry (maks 3)
     slideXProportion ≥0.99 → retry (kualitas jelek)
4. ambil piece canvas → b64
5. REKAM TRAJECTORY
     mouseDown
     sweep 0 → 0.85*W, step 3px
     SCATTER tiap 30px blok (Fisher-Yates shuffle)
     sample {pixels, rotation, piece_center}
     stop kalau piece_center.proportionX ≥ slideXProportion+15px
          atau diam 10 langkah
     sort by pixels
6. POST /shopee-image-crawl → solution px
7. RELEASE manusiawi
     maxPx = puzzleW * 0.85
     toU(px) = px/maxPx*4 - 2
     toPx(u) = (u+2)/4*maxPx
     4 oscillation passes (amplitudo 1.5 turun), step 13px
     final leg step 15px
     pause 900–2100ms sebelum nudge
     pause 750–1450ms sebelum release
```

### Konstanta anti-bot (replikasi wajib)

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

### Selector DOM Shopee

```
PUZZLE : "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false],
          div:not(#puzzleContainer) > img"
PIECE  : "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true],
          #puzzleContainer > #puzzleImgComponent"
BUTTON : "div:has(> svg + svg)"
```

---

## 7. Rotasi Kredit & Key Manager

SadCaptcha menagih per solve. Tanpa manajemen key, farm mati di tengah jalan.

```
┌ hello ─────────────────────────────────────────────────┐
│  key_manager.alive()  → key dengan credit > 0          │
│  key_manager.next()   → round-robin, kredit tertinggi  │
│  key_manager.mark()   → -1 tiap solve                  │
│  key_manager.refresh()→ GET /license/credits           │
└────────────────────────────────────────────────────────┘
```

### Failover

```
api_post_fo(body, max_keys=3):
  key1 → 401/403 → key2 → 401/403 → key3 → 401/403 → raise
```

### Watchdog

Cron `*/30 key_watchdog` menjaga minimal **2 key hidup** dan **20 kredit**.
Kalau di bawah itu → notifikasi.

### Hasil

```
10 key terdaftar
 6 alive
118 kredit total
```

---

## 8. Reputasi Nomor

Nomor Indonesia punya perilaku berbeda per prefix. Prefix `8787` di data
produksi limit-rate 100% — semua nomor dari situ ditolak Shopee.

`phone_reputation.py` menyimpan:

```
nomor   → {sukses, limit, terakhir}
prefix  → {total, limit_rate}
```

Aturan:

```
nomor sudah sukses          → skip
nomor limit 2×              → skip
prefix limit-rate ≥60%      → BLOCK semua nomor baru
       (dengan minimal 3 sampel)
```

Efek: hemat kredit (tidak menembak nomor yang pasti gagal) dan mengurangi
flag ke IP.

---

## 9. Hasil Reverse Engineering Anti-Fraud

Ini bagian yang paling mahal. Reverse penuh terhadap mesin anti-fraud Shopee.

### SAP VM — 100% ter-reverse

```
Arsitektur  : JIT compiler + bytecode interpreter (hybrid)
Bytecode    : 70.943 slot
Encoding    : opcode = ac[pc-1]     HIT=40358, MISS=0
Disassembly : 25.378 boundary, 100% match vs trace
Interpreter : 14.420 char, dispatch tree 66 node, opcode maks 999
Memory      : base 6000, stride 16 (record), ~762 KB
JIT         : V() generate JS source (46 konstruksi) → y() = eval
```

### String tables — 100% decoded

```
ae (identifier) : ae[3]="now"  ae[12]="slice"  ae[14]="var"
                  ae[15]="for" ae[16]="throw"  ae[17]="catch"
                  ae[18]="default" ae[19]="while" ae[20]="return"
aj (strings)    : 1.555 entry
tE (reflection) : "0x15"="toString"  "0x1a"="__proto__"
                  "0x1b"="hardwareConcurrency"  "0x1e"="P|I"
```

### JIT generated sources

```
800 source JS tertangkap:
  - XOR string decoder: String.fromCharCode(a[c]^c)
  - Fisher-Yates shuffle
  - Array → CSV join
  - Separator join (667)
```

### Header hasil signing

```
af-ac-enc-dat      : 16 hex = 8 byte uint64, per-request (7/7 unik)
af-ac-enc-sz-token : sz-token terenkripsi
x-sap-ri           : 26 byte [ts][nonce][seq][marker 0x1201][sig 19B]
sz-token           : b64(16B)|b64(64B)|b64(12B)|08|plat
```

### Sense SDK

```
AES-128-CBC / PKCS7
CRC: [magic 3B 75ab5a][crc32(body)&0xFF][version BE]
```

### Kesimpulan teknis

VM SAP adalah **JIT source-generator**:

1. Men-generate JS code dari bytecode (46 konstruksi)
2. `eval` source itu → fungsi hidup
3. Pakai reflection table untuk method call
4. Per-request mencetak `af-ac-enc-dat` + `af-ac-enc-sz-token`

**Jalur produksi yang dipakai:** page-context fetch (Option A). SDK
menandatangani sendiri, tidak butuh emulator offline.

---

## 10. Isi Package

```
SHOPEE_AUTOREG_PACKAGE/
├── README.md                  ← dokumen ini (untuk manusia)
├── AGENTS.md                  ← panduan untuk AI agent
├── INDEX.md                   ← peta semua dokumen
│
├── docs/                      ← dokumentasi teknis yang ditulis ulang
│   ├── PROJECT-DEEP-DIVE.md   semua detail project
│   ├── ARCHITECTURE.md        struktur & aliran data
│   ├── SIGNUP-CHAIN.md        chain signup + payload asli
│   ├── CAPTCHA-SYSTEM.md      captcha lengkap + SadCaptcha
│   ├── ANTIFRAUD-RE.md        hasil reverse VM/Sense/sz-token
│   ├── OPERATIONS.md          operasional harian
│   └── TROUBLESHOOTING.md     error & solusinya
│
├── project/                   ← KODE (329 file)
│   ├── farm_production.py     orkestrator
│   ├── worker_pool.py         worker paralel
│   ├── shopee_hold.py         chain satu akun
│   ├── captcha_cache.py       cache SQLite
│   ├── key_manager.py         rotasi kredit
│   ├── phone_reputation.py    reputasi nomor
│   ├── fpgen.py               fingerprint generator
│   ├── core/ tools/ panel/
│   └── 50 dokumen riset .md asli
│
├── reference/                 ← artefak RE
│   ├── captcha_re/            bundle JS, AES keys, hook script
│   ├── captures/              session capture (request asli)
│   └── sdk/                   string tables, VM dispatch, SadCaptcha ref
│
└── skill/                     ← 13 skill
    ├── shopee-captcha-solver/     + 5 references
    ├── sadcaptcha-shopee-api/
    ├── shopee-antifraud-reversing/
    ├── shopee-sms-otp-bypass/
    ├── shopee-token-war-stack/
    ├── shopee-va-digital-order/
    ├── shopee-bank-va-channels/
    ├── browser-signup-farming/
    ├── app-account-farming/
    ├── captcha-solver-api-integration/
    ├── farmed-account-validation/
    ├── proxy-pool-operations/
    └── browser-pool-concurrency/
```

---

## 11. Instalasi

### Prasyarat

```bash
python3 --version          # 3.12+
apt install -y xvfb        # headless display
```

### Setup

```bash
cd project
python3 -m venv /root/sniffenv
source /root/sniffenv/bin/activate
pip install -r requirements.txt
playwright install chromium
playwright install-deps
```

### Konfigurasi

```bash
cp config.example.json config.json     # lalu isi nilai asli
```

Isi yang wajib:

```json
{
  "CAP_SOLVER": "sadcaptcha",
  "CAP_API_KEY": "<license key SadCaptcha>",
  "PROXY_FILE": "proxies.txt",
  "OTP_MODE": "manual"
}
```

`proxies.txt` format:

```
http://user:pass@host:port
```

**Wajib residential Indonesia.** Datacenter IP ditolak Shopee.

---

## 12. Menjalankan

### Tes kering (tanpa jaringan)

```bash
python3 farm_browser.py --count 5 --dry-run
```

### Satu akun, manual (lihat layar captcha)

```bash
python3 auto_reg.py --mode e2e --phone 081234567890
```

### Produksi harian

```bash
# rencana 50 akun
python3 farm_production.py --plan 50

# eksekusi
python3 farm_production.py --run
```

### Panel web

```bash
python3 panel/app.py          # http://localhost:8088
```

### Cek kesehatan

```bash
python3 health_monitor.py
python3 key_manager.py status
python3 captcha_cache.py stats
python3 phone_reputation.py stats
```

---

## 13. Cron & Otomasi

```cron
*/30 *  * * *   key_watchdog.py        # jaga min 2 key hidup, 20 kredit
0    */6 * * *   account_warmer.py --warm   # panaskan akun
15   */2 * * *   proxy_health.py       # cek proxy hidup
*/20 *  * * *   prewarm_cache.py      # isi cache saat sepi (hemat kredit)
0    2  * * *   farm_production.py --plan 50
2    2  * * *   farm_production.py --run
30   */6 * * *   key_manager.py refresh
0    6  * * *   captcha_cache.py prune 30
```

Jam 02:00–05:00 dipilih karena trafik Shopee rendah dan anti-fraud lebih
longgar.

---

## 14. Hasil Terverifikasi

Semua di bawah ini punya bukti live, bukan asumsi.

| Komponen | Status | Bukti |
|---|---|---|
| Chain UI sampai captcha | ✅ | screenshot + capture request |
| `security_device_fingerprint` asli | ✅ | 139 char terekam |
| `af-ac-enc-dat` + `csrftoken` | ✅ | capture live |
| `get_settings_v2` | ✅ | HTTP 200 |
| Generator identitas + device spoof | ✅ | IMEI Luhn 200/200 |
| Store SQLite resumable | ✅ | — |
| Panel web | ✅ | port 8088 |
| Multi-akun runner | ✅ | dry-run OK |
| SadCaptcha API | ✅ | 23 kredit, endpoint benar |
| Captcha cache | ✅ | 161 puzzle, 21 pernah hit |
| Key manager | ✅ | 10 key, 6 alive, 118 kredit |
| Reputasi nomor | ✅ | prefix 8787 diblok |
| Worker rotation | ✅ | 8 nomor → 6 key berbeda |
| Failover key | ✅ | 401 → key berikutnya |
| Klasifikasi hasil | ✅ | 5/5 test pass |
| VM SAP reverse | ✅ | 100%, 70.943 slot |
| String tables | ✅ | 1.555 + 2.592 entry |
| Sense SDK crypto | ✅ | AES framing + CRC 28/28 |
| sz-token | ✅ | struktur terurai |
| End-to-end akun jadi | ⚠️ | butuh OTP sink + kredit solver |

---

## 15. Dinding yang Ditemui

Bagian ini penting dibaca sebelum menghabiskan waktu.

### Puzzle captcha tidak bisa dibaca dari DOM

Geometri puzzle di-render di **surface tertutup** SDK. Sudah dicoba semua
jalur standar:

```
DOM query              ❌  #anti_fraud_captcha = <div></div> kosong
iframe traversal       ❌  tidak ada iframe
shadow root            ❌  shadowHosts: []
getBoundingClientRect  ❌  MID RECTS: []
drawImage hook         ❌  cuma grip 44×44
WebGL texImage2D       ❌  tidak dipakai
OffscreenCanvas        ❌  hanya untuk fingerprint
```

**Yang tetap bisa:** drag → verify endpoint terpanggil (SDK encrypt sendiri).
Mekanisme solver 100% jalan, yang tidak bisa adalah membaca koordinat puzzle
dari halaman.

**Jalan keluar yang dipakai:** SadCaptcha API yang menerima gambar puzzle +
piece langsung, sehingga tidak perlu membaca rect dari DOM.

### Emulator tidak bisa jalan

```
x86_64  → native SHPSSDK crash
ARM64   → arch mismatch di emulator KVM
```

Aplikasi Shopee Android mendeteksi emulator dan crash. Jalur ini buntu.

### Cache hit rate rendah

13% (21 dari 161 puzzle). Shopee rotasi puzzle secara berkala. Cache tetap
dipakai sebagai L1 tapi tidak boleh jadi satu-satunya jalur.

### Trajectory wajib browser

`slide_piece_trajectory` harus direkam dari event mouse asli di canvas.
Tidak bisa dipalsukan dengan array buatan — pre-analyze akan menolak.

---

## 16. Pelajaran

### Cache hash-match itu rapuh

`sha256(puzzle + piece)` sebagai primary key selalu MISS, karena `piece`
berbeda tiap render walau puzzle sama. Yang benar: **content-match** pada
`puzzle_b64` saja.

### `slide_piece_trajectory` bukan opsional

Error 400 dari SadCaptcha hampir selalu karena body tidak punya field ini.
Minimal 12 baris, dan harus hasil rekaman asli.

### Pre-check reputasi lebih murah daripada retry

Satu kali percobaan gagal = 1 kredit hangus + flag IP naik. Skip nomor
bermasalah sebelum jalan menghemat dua-duanya.

### `security_device_fingerprint` tidak bisa dipalsukan

Formatnya `base64|base64|hex8|op|ver`, dibentuk engine Tongdun dari 7+
sumber fingerprint. Requests polos tidak akan pernah lolos.

### Page-context fetch menghemat berhari-hari kerja

Daripada reimplementasi VM signer, panggil `fetch()` dari dalam halaman.
SDK menandatangani sendiri. Hasilnya identik dengan user asli.

### Satu proxy jangan dipakai dua worker

Dua akun registrasi dari IP sama dalam waktu dekat = flag otomatis. Proxy
lock wajib.

---

## 17. Untuk AI Agent

Kalau kamu agent yang membaca ini: **baca `AGENTS.md` dulu**, bukan file ini.

`README.md` ditulis untuk manusia — naratif, berurutan, dengan konteks bisnis.
`AGENTS.md` ditulis untukmu — tabel keputusan, invariant, titik masuk kode,
dan aturan yang tidak boleh dilanggar saat mengubah apa pun.

Dokumen pendamping:

- `docs/PROJECT-DEEP-DIVE.md` — semua detail tanpa narasi
- `docs/ARCHITECTURE.md` — aliran data dan tanggung jawab modul
- `docs/CAPTCHA-SYSTEM.md` — protokol SadCaptcha lengkap
- `docs/TROUBLESHOOTING.md` — gejala → penyebab → fix

---

**Stack:** Python 3.12 · Playwright · SadCaptcha API · SQLite · Crypoto
**Dokumen riset:** 50 file `.md` di `project/`
**Skill:** 13 skill di `skill/`
