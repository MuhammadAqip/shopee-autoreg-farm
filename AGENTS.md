# AGENTS.md — Panduan untuk AI Agent

Dokumen ini untuk agent yang akan **membaca, mengubah, atau menjalankan** codebase
ini. Ditulis sebagai referensi operasional, bukan narasi. Baca ini dulu sebelum
menyentuh file apa pun.

`README.md` = untuk manusia (naratif, konteks bisnis).
`AGENTS.md` = untukmu (invariant, titik masuk, aturan).

---

## 0. Ringkasan 30 Detik

Farm registrasi akun Shopee. Browser Playwright menjalankan chain signup,
captcha diselesaikan lewat SadCaptcha API, hasilnya akun + cookie.

**Yang tidak boleh kamu lakukan:** menjalankan `farm_production.py --run`
tanpa diminta eksplisit. Itu menghabiskan kredit solver dan membuat akun nyata.

**Yang aman dilakukan tanpa izin:** baca file, jalankan `--dry-run`, jalankan
`--stats`, jalankan test, edit dokumen.

---

## 1. Peta Cepat

| Mau apa | File | Fungsi |
|---|---|---|
| Jalankan satu akun | `project/auto_reg.py` | `--mode e2e --phone <nomor>` |
| Jalankan batch | `project/farm_production.py` | `--plan N` / `--run` |
| Runner browser | `project/farm_browser.py` | `--count N --dry-run` |
| Chain satu akun | `project/shopee_hold.py` | `hold_account(phone, proxy, key)` |
| Worker paralel | `project/worker_pool.py` | `run_pool(phones)` |
| Cache captcha | `project/captcha_cache.py` | `stats` / `prune N` |
| Kredit key | `project/key_manager.py` | `status` / `refresh` |
| Reputasi nomor | `project/phone_reputation.py` | `check(phone)` / `stats` |
| Fingerprint | `project/fpgen.py` | `gen_mobile()` / `gen_pc()` |
| Panel web | `project/panel/app.py` | port 8088 |
| Validasi cookie | `project/account_validator.py` | `check(cookie)` |
| Panaskan akun | `project/account_warmer.py` | `--warm` |

---

## 2. Model Data

### Akun (SQLite, `core/store.py`)

```python
{
  "Username":      str,       # nama user Shopee
  "Password":      str,
  "Nomor":         str,       # 08xxx atau 628xxx
  "UserId":        str,       # kosong kalau gagal
  "Fingerprint":   str,       # p1|p2|p3|08|platform
  "DeviceID":      str,       # spc_device_id
  "Cookie":        str,       # SPC_U=...; SPC_ST=...
  "status":        str,       # ready | limit | failed
  "created_at":    int,
}
```

### State field yang sering salah

| Field | Tipe | Jebakan |
|---|---|---|
| `Nomor` | `str` | Bisa `08…` atau `628…`. Normalisasi sebelum dipakai |
| `UserId` | `str` | String kosong = akun gagal. Jangan cek `is None` |
| `Fingerprint` | `str` | Harus konsisten per akun — jangan regenerate di tengah |
| `status` | `str` | `limit` bukan `failed` — beda penanganan |

### Cache captcha

```
PRIMARY KEY : puzzle_b64   (content match, BUKAN hash)
kolom       : puzzle_b64, answer_x, hits, verified, created_at
WAL mode    : reader tidak diblok writer
verified    : hits >= 2
```

**Jangan pernah** mengubah primary key kembali ke `sha256(puzzle+piece)` —
`piece` berbeda tiap render sehingga selalu MISS.

---

## 3. Invariant — Jangan Dilanggar

Enam aturan di bawah ini sudah dibayar dengan waktu debug. Melanggar satu saja
akan bikin farm gagal tanpa error yang jelas.

### I1 — Satu proxy = satu worker bersamaan

Dua akun registrasi dari IP sama akan kena flag. `worker_pool.py` memakai
`proxy_lock` untuk ini. **Jangan** hapus atau bypass.

### I2 — Fingerprint harus konsisten dalam satu chain

Regenerate `fpgen` di tengah chain = `security_device_fingerprint` berubah =
server menolak. Satu akun, satu fingerprint, dari awal sampai akhir.

### I3 — Jangan retry pada gate "Identifikasi Tambahan"

Itu LIMIT, bukan error jaringan. Retry = buang kredit + naikkan skor risiko
IP. Di kode: `classify()` mengembalikan `limit`, dan caller harus skip.

### I4 — `slide_piece_trajectory` minimal 12 baris

SadCaptcha menolak body tanpa field ini atau dengan kurang dari 12 baris.
Error yang muncul cuma `400` tanpa detail.

### I5 — Cache primary key = `puzzle_b64`

Lihat bagian Model Data. Ini pernah bikin hit rate 0%.

### I6 — Signing lewat page-context fetch

Jangan pernah mencoba membangun `x-sap-sec` / `af-ac-enc-dat` secara offline
untuk produksi. Pakai `page.evaluate(fetch)`. Emulator offline ada di
`vm_engine.py` tapi hanya untuk riset.

---

## 4. Alur yang Benar

### Menjalankan satu akun (aman, dengan output)

```bash
cd project
source /root/sniffenv/bin/activate

# dry-run dulu — tidak menyentuh jaringan
python3 auto_reg.py --mode dry --phone 081234567890

# nyata (butuh key + proxy + OTP sink)
python3 auto_reg.py --mode e2e --phone 081234567890
```

### Batch

```bash
# 1. RENCANA — tidak eksekusi, cuma daftar nomor yang akan dipakai
python3 farm_production.py --plan 50

# 2. REVIEW output plan (json tersimpan)
cat farm_out/plan_*.json

# 3. EKSEKUSI — baru setelah plan disetujui
python3 farm_production.py --run
```

Selalu `--plan` dulu. `--run` tanpa plan akan memilih nomor acak tanpa
pre-check reputasi yang sudah di-review.

### Diagnostik

```bash
python3 key_manager.py status          # kredit per key
python3 captcha_cache.py stats         # hit rate cache
python3 phone_reputation.py stats      # prefix mana yang diblok
python3 health_monitor.py              # overall
```

---

## 5. Titik Masuk Kode

### `shopee_hold.hold_account()`

```python
def hold_account(phone, proxy=None, key="auto") -> dict:
    """
    Returns:
      {"status": "ready",  "user_id": ..., "cookie": ..., "username": ...}
      {"status": "limit",  "reason": "Identifikasi Tambahan"}
      {"status": "failed", "error": str}
    """
```

**Caller harus** menangani tiga status berbeda. Menganggap semua non-`ready`
sebagai `failed` akan merusak statistik reputasi.

### `worker_pool.run_pool()`

```python
def run_pool(phones, concurrency=2) -> list[dict]:
```

Di dalamnya:

1. Pre-check reputasi per nomor
2. Ambil proxy lock
3. Ambil key dari `KeyManager`
4. Panggil `hold_account`
5. Klasifikasi + simpan reputasi + lepas lock

### `captcha_cache`

```python
get(puzzle_b64)                    -> answer_x | None
put(puzzle_b64, answer_x)          -> None
stats()                            -> dict
prune(max_age_days=30)             -> int
```

### `key_manager`

```python
KeyManager.instance()
  .alive()      -> list[key]
  .next()       -> key
  .mark(key)    -> None    # -1 kredit
  .refresh()    -> None    # GET /license/credits
```

---

## 6. Konfigurasi

`config.json` di root `project/`:

```json
{
  "CAP_SOLVER": "sadcaptcha",
  "CAP_API_KEY": "<license key>",
  "PROXY_FILE": "proxies.txt",
  "OTP_MODE": "manual",
  "HEADLESS": true,
  "MAX_CONCURRENCY": 2
}
```

| Field | Nilai valid | Efek |
|---|---|---|
| `CAP_SOLVER` | `sadcaptcha` | solver yang dipakai |
| `OTP_MODE` | `manual` \| `http` \| `wa` | cara ambil OTP |
| `HEADLESS` | `true` \| `false` | `false` butuh xvfb |
| `MAX_CONCURRENCY` | 1–4 | worker paralel |

**Jangan** set `MAX_CONCURRENCY` > 4. RAM habis dan flag IP naik.

---

## 7. Error → Tindakan

| Gejala | Penyebab | Tindakan |
|---|---|---|
| `400` dari SadCaptcha | body tanpa `slide_piece_trajectory` | cek field, minimal 12 baris |
| `401` / `403` SadCaptcha | kredit habis / key mati | `key_manager.refresh()`, failover |
| `need_captcha: true` terus | captcha tidak terselesaikan | cek trajectory + selector DOM |
| "Identifikasi Tambahan" | anti-fraud flag nomor | `limit`, skip, catat |
| `Pixel mismatch` | jawaban solver salah | pre-analyze ulang, jangan retry buta |
| Browser crash | RAM habis | turunkan `MAX_CONCURRENCY` |
| `puzzle render` 1/3 kali | captcha flaky | jeda antar percobaan |
| Cache tidak hit | primary key salah | harus `puzzle_b64`, bukan hash |
| Semua nomor diblok | prefix buruk | cek `phone_reputation.py stats` |
| `x-sap-sec` hilang | halaman navigate ulang | pastikan request dari halaman aktif |

---

## 8. Yang Tidak Boleh Diubah Tanpa Riset

| Bagian | Kenapa |
|---|---|
| `captcha_cache` primary key | riwayat: hash-match → 0% hit |
| `proxy_lock` di worker_pool | hapus = akun saling flag |
| `classify()` prioritas | limit > ready > failed; urutan salah = statistik rusak |
| Konstanta gesture | nilai dikalibrasi terhadap anti-bot; ubah = captcha gagal |
| Selector DOM captcha | berubah kalau Shopee ubah markup |
| `page.evaluate(fetch)` | ganti ke `requests` = 100% gagal |

---

## 9. Test

```bash
cd project

# chain signup tanpa jaringan
python3 auto_reg.py --mode dry --phone 081234567890

# cache
python3 captcha_cache.py stats
python3 -c "from captcha_cache import Cache; c=Cache(); print(c.get('<b64>'))"

# reputasi
python3 phone_reputation.py stats

# key
python3 key_manager.py status
python3 key_manager.py refresh
```

Tidak ada test suite otomatis. Verifikasi dilakukan lewat skrip di atas dan
log di `farm_out/`.

---

## 10. Log & Output

```
farm_out/
├── plan_YYYYMMDD_HHMMSS.json    rencana
├── run_YYYYMMDD_HHMMSS.json     hasil eksekusi
└── log_YYYYMMDD.log             log mentah
```

Format `run_*.json`:

```json
{
  "total": 50,
  "ready": 31,
  "limit": 14,
  "failed": 5,
  "credits_used": 19,
  "results": [
    {"phone": "08xxx", "status": "ready", "user_id": "...", "at": 1793...}
  ]
}
```

---

## 11. Urutan Membaca untuk Agent Baru

```
1. AGENTS.md              ← kamu di sini
2. docs/ARCHITECTURE.md   ← aliran data
3. docs/SIGNUP-CHAIN.md   ← payload asli, urutan request
4. project/shopee_hold.py ← chain nyata
5. project/worker_pool.py ← konkurensi
6. docs/CAPTCHA-SYSTEM.md ← protokol solver
7. docs/TROUBLESHOOTING.md
```

Jangan mulai dari `project/` — 329 file terlalu banyak tanpa peta.

---

## 12. Dokumen Pendamping

| File | Untuk apa |
|---|---|
| `README.md` | konteks manusia, fitur, cara pakai |
| `INDEX.md` | peta semua `.md` |
| `docs/PROJECT-DEEP-DIVE.md` | semua detail, tanpa narasi |
| `docs/ARCHITECTURE.md` | modul + aliran data |
| `docs/SIGNUP-CHAIN.md` | request/response asli |
| `docs/CAPTCHA-SYSTEM.md` | SadCaptcha + trajectory |
| `docs/ANTIFRAUD-RE.md` | VM SAP, Sense, sz-token |
| `docs/OPERATIONS.md` | cron, monitoring, runbook |
| `docs/TROUBLESHOOTING.md` | error → fix |
| `skill/*/SKILL.md` | 13 skill operasional |

---

## 13. Skill yang Relevan

Kalau tugasmu menyentuh salah satu area ini, baca skill-nya dulu:

| Tugas | Skill |
|---|---|
| Captcha Shopee | `skill/shopee-captcha-solver/SKILL.md` |
| API SadCaptcha | `skill/sadcaptcha-shopee-api/SKILL.md` |
| Reverse anti-fraud | `skill/shopee-antifraud-reversing/SKILL.md` |
| Registrasi OTP | `skill/shopee-sms-otp-bypass/SKILL.md` |
| Farm browser | `skill/browser-signup-farming/SKILL.md` |
| Farm akun | `skill/app-account-farming/SKILL.md` |
| Integrasi solver | `skill/captcha-solver-api-integration/SKILL.md` |
| Validasi akun | `skill/farmed-account-validation/SKILL.md` |
| Proxy pool | `skill/proxy-pool-operations/SKILL.md` |
| Browser pool | `skill/browser-pool-concurrency/SKILL.md` |
| Order digital | `skill/shopee-va-digital-order/SKILL.md` |
| Channel VA | `skill/shopee-bank-va-channels/SKILL.md` |
| War token | `skill/shopee-token-war-stack/SKILL.md` |

---

## 14. Aturan Terakhir

**Jangan menjalankan `--run` tanpa diminta.** Ini menghabiskan kredit nyata
dan membuat akun nyata.

**Jangan menghapus file di `reference/`.** Isinya artefak reverse engineering
yang butuh berhari-hari untuk dibuat ulang.

**Jangan commit kredensial.** `config.json`, `proxies.txt`, database
`captcha_cache.db`, dan `farm_out/` masuk `.gitignore`. Jangan di-force add.

**Kalau bingung, baca `docs/TROUBLESHOOTING.md` dulu** sebelum mengubah kode.
Sebagian besar "bug" di repo ini adalah perilaku Shopee yang sudah
didokumentasikan.
