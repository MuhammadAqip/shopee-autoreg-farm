# 🚀 OPTION A — PRODUCTION SETUP (STATUS)

## ✅ YANG UDAH JADI

### 1. Page-context fetch (SDK auto-sign) — **TERBUKTI 100%**
```
7 signed requests captured live:
  af-ac-enc-dat      : 16 hex (8 byte, per-request token)
  af-ac-enc-sz-token : SDK-generated
  x-sap-ri/x-sap-sec : auto fresh tiap request
→ fetch dari dalam page = SDK auto-sign. Tanpa reverse offline.
```
Fix: `pure_signup.py` — buang header `af-ac-enc-dat:''` (SDK yang inject).

### 2. Captcha cache resolver — **TERBUKTI**
```
cache hit → offset exact (117, 138, 156) = GT×280 ✅
154 puzzles cached, WAL mode aktif (fix DB lock)
captcha_resolve.py: cache → local gap_v6 → miss
```

### 3. Production scheduler — **INSTALLED**
```
farm_production.py:
  --plan N    : jadwal N akun, window 02:00-05:00, jarak 10-30min
  --run       : eksekusi per jadwal
  --test-now  : 1 akun sekarang
  nomor random (prefix operator valid)
  klasifikasi: ready(🟢) / limit(🟡) / failed(🔴)

crontab:
  0 2 * * *  farm_production.py --plan 50
  2 2 * * *  farm_production.py --run
```

### 4. Notif auto-detect — **WORKS**
```
detect_chat_id(): env → bot getUpdates → fallback 7341376283
notify('🟢/🟡/🔴 ...') → terkirim ✅
```

### 5. Pipeline test — **JALAN**
```
shopee_hold.py → STATE=CAPTCHA ✅ (fingerprint inject OK)
```

---

## ⚠️ SISA / BLOCKER
1. **Captcha solver API** — endpoint `shopee-image-crawl` balas 404/400 (path berubah)
   → SOLUSI: cache-first resolver (jalan) + prewarm agresif saat solver normal
2. **Cache hit-rate** — Shopee rotate captcha; hit rendah untuk puzzle baru
   → SOLUSI: prewarm (solve banyak → isi cache) ATAU fix endpoint solver
3. **local gap_v6** — akurasi rendah (148 vs GT 117) → perlu kalibrasi

---

## 🎯 JALUR PRODUKSI SAAT INI
```
1. Cron 02:00 → plan 50 akun
2. Cron 02:02 → run: tiap akun
   - browser + fingerprint
   - captcha: cache_resolve (hit→instant, miss→local/API)
   - OTP via WA
   - sukses → akun ready + notif 🟢
3. Report per-akun ke Telegram
```

## 📋 REKOMENDASI LANJUTAN
- **P1:** fix endpoint solver SadCaptcha (path berubah) → restore prewarm
- **P2:** kalibrasi gap_v6 (atas cache GT 154 sample) → local solve akurat
- **P3:** jalankan test 1 akun jam 02:00-05:00 (bukan jam ramai)
