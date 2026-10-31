# ARCHITECTURE — Struktur & Aliran Data

Referensi modul: siapa memanggil siapa, data mengalir ke mana, dan siapa
bertanggung jawab atas apa.

---

## 1. Diagram Lapisan

```
┌────────────────────────────────────────────────────────────────────┐
│ ENTRY POINT                                                        │
│   farm_production.py   (cron 02:00)                                │
│   auto_reg.py          (manual, satu akun)                         │
│   panel/app.py         (web UI, port 8088)                         │
└────────────────────────────┬───────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────┐
│ ORKESTRASI                                                         │
│   worker_pool.py                                                   │
│     ├─ reputation.check(phone)      → ALLOW / BLOCK                │
│     ├─ proxy_pool.acquire(account)  → proxy (locked)               │
│     ├─ key_manager.next()           → license key                  │
│     └─ shopee_hold.hold_account()   → result dict                  │
└────────────────────────────┬───────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────┐
│ CHAIN SATU AKUN — shopee_hold.py                                   │
│                                                                    │
│   fpgen + core/device     → identitas + fingerprint                │
│   core/shopee_client      → endpoint wrapper                       │
│   playwright              → browser + page-context fetch           │
│   captcha_cache           → cache L1                               │
│   sadcaptcha_client       → API L2                                 │
│   tools/proxy (OTP sink)  → ambil OTP                              │
└────────────────────────────┬───────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────┐
│ PERSISTENSI                                                        │
│   core/store.py        → SQLite akun (resumable)                   │
│   captcha_cache        → SQLite puzzle                             │
│   phone_reputation     → SQLite/JSON reputasi                      │
│   key_store            → kredensial key                            │
│   farm_out/*.json      → hasil per run                             │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. Tanggung Jawab Modul

| Modul | Tanggung jawab | Tidak boleh |
|---|---|---|
| `farm_production` | Plan, jadwal, report | Buka browser langsung |
| `worker_pool` | Konkurensi, locking, klasifikasi | Tahu detail captcha |
| `shopee_hold` | Chain lengkap satu akun | Mengatur konkurensi |
| `farm_browser` | Multi-akun sederhana | Konkurensi kompleks |
| `auto_reg` | Satu akun, debug | Batch |
| `captcha_cache` | Simpan & cari jawaban | Panggil API |
| `sadcaptcha_client` | Protokol API | Cache |
| `key_manager` | Rotasi & kredit | Memilih nomor |
| `phone_reputation` | Statistik nomor/prefix | Mengambil keputusan skip |
| `fpgen` | Identitas & device | Buka browser |
| `core/store` | Persistensi akun | Logika bisnis |
| `panel/app` | UI baca/tulis store | Menjalankan chain |

Aturan umum: **lapisan atas memanggil lapisan bawah, tidak pernah sebaliknya.**

---

## 3. Aliran Data — Satu Akun

```
phone ─────────────────────────────────────────────────────┐
  │                                                          │
  ▼                                                          │
[reputation.check]                                           │
  │ BLOCK → return {"status":"skipped"}                      │
  ▼ ALLOW                                                    │
[proxy_pool.acquire]  ← lock                               │
  ▼                                                          │
[key_manager.next]                                           │
  ▼                                                          │
[fpgen.gen_identity]  ─┬─► name, email, password             │
[core/device.gen]     └─► model, imei, spc_device_id         │
  ▼                                                          │
[browser launch]  (Playwright, headless)                     │
  │                                                          │
  ├─ goto /buyer/signup                                      │
  ├─ gate bahasa                                            │
  ├─ isi phone                                              │
  ├─ TOS + Berikutnya + Setuju                              │
  │                                                          │
  ├─ page.evaluate(fetch, get_settings_v2)                   │
  │     ↳ SDK tandatangani otomatis                          │
  │     ← {need_captcha: true}                               │
  │                                                          │
  ├─ [captcha_cache.get(puzzle_b64)]                         │
  │     HIT  → answer_x                                     │
  │     MISS → pre-analyze → trajectory → solve → cache.put │
  │                                                          │
  ├─ page.evaluate(fetch, send_otp)                          │
  │                                                          │
  ├─ [OTP sink] ← SMS/WA                                    │
  ├─ page.evaluate(fetch, verify_otp)                        │
  │                                                          │
  └─ cookie SPC_U + SPC_ST                                  │
  ▼                                                          │
[store.save_account]                                         │
[reputation.record(phone, result)]                           │
[key_manager.mark(key)]                                      │
[proxy_pool.release]  ← unlock                               │
  ▼                                                          │
return {"status":"ready", "user_id":..., "cookie":...} ◄─────┘
```

---

## 4. Aliran Data — Regenerasi (resume)

Store SQLite mendukung resume. Kalau proses mati di tengah batch:

```
[startup]
  ↓
store.pending()  → akun dengan status=None
  ↓
[untuk tiap pending]
  ├─ punya cookie valid?  → skip, tandai ready
  ├─ punya user_id?       → login ulang (account_login_repair)
  └─ tidak ada apa-apa    → jalankan chain dari awal
```

Ini yang membuat batch 50 akun bisa dilanjutkan setelah crash.

---

## 5. Konkurensi

### Model

```
farm_production
  └─ worker_pool(concurrency=2)
       ├─ worker-1  →  proxy A  →  key-1  →  chain
       └─ worker-2  →  proxy B  →  key-2  →  chain
```

### Locking

```python
class ProxyPool:
    def acquire(self, timeout=120):
        with self._lock:
            for p in self._proxies:
                if not p.in_use:
                    p.in_use = True
                    return p
        wait / raise TimeoutError

    def release(self, p):
        with self._lock:
            p.in_use = False
```

Satu proxy tidak bisa dipakai dua worker bersamaan. Kalau pool habis,
worker menunggu.

### Batas

| Setting | Nilai | Alasan |
|---|---|---|
| `concurrency` | 2 (default), 4 (max) | RAM + flag IP |
| RAM per browser | ~350 MB | Chromium + context |
| Akun per jam | 6–12 | jeda antar akun |

### Jeda antar akun

```python
delay = random.randint(600, 1800)     # 10–30 menit
```

Tanpa jeda: registrasi berturut = pola bot = flag.

---

## 6. State Akun

```
        ┌──────────┐
        │  None    │  (baru, belum dicoba)
        └────┬─────┘
             │ chain jalan
             ▼
     ┌───────────────┐
     │  in_progress  │
     └───┬───────┬───┘
         │       │
    sukses│       │gagal
         ▼       ▼
   ┌─────────┐  ┌────────┐
   │  ready  │  │ limit  │ ◄── "Identifikasi Tambahan"
   └────┬────┘  └────┬───┘
        │            │
        │            └──► tidak di-retry
        │
   ┌────▼─────────────┐
   │  warming/active  │  (account_warmer)
   └──────────────────┘

   ┌────────┐
   │ failed │ ◄── error lain, bisa di-retry
   └────────┘
```

Perbedaan `limit` vs `failed` penting:

- `limit` = nomor ditandai, **jangan** retry
- `failed` = error teknis, boleh retry

Menganggap keduanya sama akan merusak statistik reputasi.

---

## 7. Ketergantungan Eksternal

```
Playwright ──► Chromium (bundled)
SadCaptcha ──► HTTPS API (license key per-request)
Proxy      ──► HTTP/SOCKS residential
OTP        ──► manual / HTTP provider / WA bridge
Nomor HP   ──► eksternal (tidak dikelola repo ini)
```

Tidak ada `service` yang harus jalan. Semua dependency eksternal dipanggil
langsung.

---

## 8. Batas Keamanan

| Data | Lokasi | Tidak boleh |
|---|---|---|
| License key | `config.json` | commit |
| Proxy credential | `proxies.txt` | commit |
| Cookie akun | SQLite store | log ke stdout |
| Password akun | SQLite store | log |
| OTP | file/memory | persist setelah dipakai |

`.gitignore` menutup semua. Kalau menambah file kredensial baru, tambahkan ke
`.gitignore` di commit yang sama.

---

## 9. Titik Ekstensi

Kalau perlu menambah kemampuan baru:

| Kebutuhan | Modifikasi di |
|---|---|
| Solver baru | `tools/captcha.py` (adapter) |
| Provider OTP baru | `tools/proxy.py` (`*OTP` class) |
| Platform baru | `core/shopee_client.py` + `shopee_hold.py` |
| Metrik baru | `chart_stats.py` + panel |
| Backend proxy baru | `tools/proxy.py` |
| Format export baru | `panel/app.py` |

Jangan menambah logika baru ke `worker_pool.py` kecuali menyangkut konkurensi.
Modul itu harus tetap kecil dan jelas.
