# Opsi AB — Template-Match + Jawaban: Layanan Solver Pihak Ketiga

**Tanggal:** 2026-10-15

## 🔴 PERTANYAAN MAKER: Adakah layanan solver Shopee captcha?

**JAWABAN (hasil probe 2captcha/capmonster, 2026-10-15): TIDAK ADA.**

### Daftar captcha yang didukung 2captcha (dari halaman resmi):
reCAPTCHA (v2/v3/Enterprise), hCaptcha, Cloudflare Turnstile, Arkose(FunCaptcha),
Amazon/WAF, DataDome, GeeTest, **Capy Puzzle**, **Temu captcha**, Binance,
Slider Captcha (generic), Click Captcha, Rotate, Image/Text/Normal,
Lemincaptcha, MTCaptcha, CyberSiARA, Prosopo, Friendly, Tencent, dll.

**→ Shopee TIDAK ada di daftar.** Capmonster.id → hanya geetest/hcaptcha/recaptcha.

### Kesimpulan
- Layanan populer (2captcha, capsolver, anti-captcha, capmonster) **tidak support Shopee**
  (Shopee pakai captcha CUSTOM `advanced_slider`).
- **Mendekati (mungkin bisa dicoba):**
  - **Slider Captcha (generic)** — kalau puzzle = slider gambar standar (kirim image + track)
  - **Capy Puzzle Captcha** — puzzle-piece; Shopee mirip
  - **Temu captcha** — marketplace SEA, mirip Shopee
- **Alternatif:** 2captcha/ticket custom (enterprise), atau jasa human-solver manual.

### Realitas
Deliverable kita (solver sendiri) **lebih murah + full-control** — tinggal presisi celah.

## 🔬 Opsi AB: Template-Match hole-shape

`tools/gap_v6.py` — matchTemplate(piece, background):
```
puz0: hole 77.9% (score 0.423)
puz1: hole 51.4% (score 0.470)
puz2: hole 48.9% (score 0.238)
puz3: hole 52.5% (score 0.323)
puz4: hole 50.0% (score 0.242)
puz5: hole 49.6% (score 0.167)
```
Sebagian besar **~49-52%** (celah tengah), beberapa 78%. Match score rendah
(piece ≠ hole: penuh vs kosong).

## 📊 Konsensus detektor

| Versi | Metode | Hole |
|---|---|---|
| v5 | dark-blob | 40-54% |
| v6 | template-match | 49-78% |
| **Konsensus** | — | **~48-54% (tengah)** |

Celah **bervariasi per puzzle** (Shopee randomize) → offset 139-218px.

## 📊 Status FINAL (A→AB)

| Komponen | Status |
|---|:-:|
| Endpoint + kripto + jenis | ✅ |
| **Proxy Indonesia** | ✅ |
| **Pipeline otomatis penuh** | ✅ |
| Modal/TOS/submit/captcha | ✅ |
| Piece detect | ✅ |
| Celah detect (v5/v6) | ⚠️ ~48-54% |
| Drag + verify + multi (≤6) | ✅ |
| Lolos → OTP | ❌ |
| **Solver pihak ketiga** | ❌ tidak ada yg support Shopee |

## 🧱 Sisa: 1 dinding (presisi celah)

Detektor beri ~48-54% (konsensus) tapi belum presisi sub-pixel pada background
kompleks. Solusi: model vision inline / template-match dgn mask piece.
