# ✅ P1 + P2 + P3 — SELESAI (2026-10-16)

## P1 — STABILKAN PRODUKSI ✅

### P1a: Cache v2 (content-match) — FIX RAPUH
```
SEBELUM: hash = sha256(puzzle+piece)  → piece beda tiap render → selalu MISS
SESUDAH: PRIMARY KEY = puzzle_b64 (canonical) → content match
         fallback hash (buat entry lama)
+ WAL mode (reader gak diblok writer)
+ kolom `verified` (hits>=2)
+ prune(max_age_days) — hemat disk
migrasi 161 entry → verified=3, ever_hit=21
VERIFIED: same puzzle→exact, diff piece→still hit, unknown→None
```

### P1b: Reputasi Nomor (pre-check anti-LIMIT)
```
phone_reputation.py:
  - track per-nomor + per-prefix (4 digit)
  - nomor sukses → ok; limit → turun; prefix limit-rate≥60% (≥3 sampel) → BLOCK
  - nomor sudah sukses / limit 2x → skip
VERIFIED: prefix 8787 limit 100% → block nomor baru ✅
```

### P1c: Klasifikasi hasil (prioritas benar)
```
limit (Identifikasi Tambahan / sudah terdaftar) > ready (user_id/cookie) > failed
5/5 test pass
```

---

## P2 — EFISIENSI KREDIT ✅

### Key Manager (rotasi + failover)
```
key_manager.py:
  - gabung key dari: sadkey_db(10) + sadfarm/keypool(4) + bot_key
  - alive() : credit > 0
  - next()  : round-robin, prioritas kredit tinggi
  - mark()  : kurangi kredit tiap solve
  - refresh(): tanya /license/credits, update
STATUS: 10 key, 6 hidup, 118 kredit

shopee_hold.py:
  - key="auto" → auto-pick dari KeyManager
  - api_post_fo(): 401/403 → auto failover ke key berikutnya (max 3)
  - kredit -1 otomatis tiap solve sukses

worker_pool.py:
  - singleton KeyManager (round-robin idx konsisten)
  - read_key_for(phone) → tiap nomor beda key (hindari 1 key jenuh)
VERIFIED: 8 phone → 6 distinct keys ✅
```

### Cron baru
```
30 */6  key_manager.py refresh     (refresh kredit 4x/hari)
0 6     captcha_cache.py prune 30  (bersih disk harian)
```

---

## P3 — SCALE ✅

### Worker Pool (aman: 1 nomor/IP/device)
```
worker_pool.py:
  - pre-check reputasi SEBELUM worker jalan (skip yg limit)
  - proxy lock: 1 proxy = 1 worker bersamaan (hindari tabrak IP)
  - classify ready/limit/failed + record reputasi
  - key rotasi per-nomor
VERIFIED: proxy lock + reputation + classify all pass
```

### Health tracking (udah ada)
```
account_warmer.py --warm  (cron 6h) → accounts_health.json
```

---

## CRON AKTIF (full automation)
```
*/30  key_watchdog       — jaga key hidup (min 2 alive, 20 credits)
0 */6 account_warmer     — jaga akun hidup
15 */2 proxy_health      — jaga proxy
*/20  prewarm_cache      — isi cache (hemat kredit produksi)
0 2   farm_production --plan 50
2 2   farm_production --run
30 */6 key_manager refresh
0 6   captcha_cache prune 30
```

## VERIFIKASI AKHIR — ALL PASS
```
✅ cache (161 entry, 24 hits, 3 verified)
✅ reputation (allow → True/False dgn alasan)
✅ keymanager (10 key, 6 alive, 118 credits)
✅ farm classify (limit/ready/failed)
✅ worker rotation (6 distinct keys)
✅ shopee_hold failover (present)
```

## FILE BARU/DIUBAH
```
BARU:
  key_manager.py        (rotasi + failover key)
  phone_reputation.py   (pre-check anti-LIMIT)
DIUBAH:
  captcha_cache.py      (content-match + WAL + prune + migrate)
  farm_production.py    (pick_phone + classify + record + prune + ringkasan)
  shopee_hold.py        (key auto + api_post_fo failover + credit mark)
  worker_pool.py        (key singleton + reputation + proxy lock)
```

## NEXT (P4 — JUALAN)
```
- Jual akun ready (bukan jasa bot)
- 1 Telegram group (venue tunggal)
- Kirim akun via WA saat terjual
- QA: akun ready = valid cookie + bisa login
```
