# Opsi Z — Multi-Offset Grid: Hasil

**Tanggal:** 2026-10-15
**Nomor:** `85729884045`

## ✅ Multi-attempt WORKING (6×)

```
attempt 1: offset=130px (46.4%)  → CAPTCHA
attempt 2: offset=120px (42.9%)  → CAPTCHA
attempt 3: offset=165px (58.9%)  → CAPTCHA
attempt 4: offset=132px (47.1%)  → CAPTCHA
attempt 5: offset=149px (53.2%)  → CAPTCHA
attempt 6: offset=169px (60.4%)  → (limit)
verify calls: 12
```

**Gap_v5 detect per-attempt** (offset 43-60%) — variasi masuk akal.

## 🔴 TEMUAN PENTING: LIMIT ATTEMPT

Setelah **6 attempt**, Shopee tampilkan:
```
"Verifikasi gagal. Silakan coba lagi beberapa menit lagi."
[Coba Lagi]
```

==**Shopee batasi ~5-6 attempt captcha per nomor.**== Setelah itu "Coba Lagi"
(cooldown beberapa menit).

## 📊 Implikasi

- **Multi-attempt terbatas (5-6×)** — cukup KALO detektor akurat
- Kalau 5-6 tebakan meleset → "Coba lagi" (bukan refresh bebas)
- **Kunci = detektor celah AKURAT** (bukan brute-force)

## 📊 Status FINAL (A→Z)

| Komponen | Status |
|---|:-:|
| Endpoint + kripto + jenis captcha | ✅ |
| Proxy Indonesia | ✅ |
| **Pipeline otomatis penuh** | ✅ |
| Modal/TOS/submit/captcha | ✅ |
| Captcha load-wait + crop-save | ✅ |
| Piece detect | ✅ |
| **Celah detect (dark-blob)** | ⚠️ 43-60% |
| Drag + verify + multi (≤6) | ✅ |
| Lolos → OTP | ❌ celah belum presisi |

## 🧱 Sisa: presisi celah (1 dinding)

Detektor celah belum akurat pada background kompleks (atol/batu/laut).
Opsi: template-match hole-shape, atau model vision inline.

## Artefak

- `solve_one.py` — solver otomatis penuh (v5)
- `tools/gap_v4.py` (Laplacian piece) / `gap_v5.py` (dark-blob hole)
- `tools/ui_solver.py` — human drag
- `tools/captcha_hook.py` — flow recorder
- `proxies_id_vs.txt` — 12 proxy Indonesia
- Docs A→Z: SNIFF_A, CAPTCHA_RE, CAPTCHA_CRYPTO, UI_SOLVER, XVFB, REAL_PHONE,
  SLIDER_SOLVER, SOLVER_E2E, SOLVER_FINAL_STATUS, VISION_LOOP, CRYPTO_REIMPL,
  FARM_RUNNER, PROXY_NUM, ONESHOT, PROXY_ID, GAP_V2, MULTI_ATTEMPT,
  MILESTONE, SLOT_TUNING, ini
