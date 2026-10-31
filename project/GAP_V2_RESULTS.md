# Opsi W — Gap Detection Akurat: Hasil

**Tanggal:** 2026-10-15

## 🔬 Analisis mekanik puzzle (temuan baru)

Crop presisi puzzle (rect 500,353,280,150) + zoom 4x → struktur:

- **Slot/celah putih (outline)** di **kiri ~8%** (x≈20-160/1120 @4x)
- **2 potongan gelap** di tengah (x≈34% dan ~53%)
- Instruksi: "Geser untuk menyelesaikan puzzle"
- Grip 44×44 di bawah

RE bundle → **5 tipe verify**:
```
verifySliderCaptcha / verifyAnimatedCaptcha / verifyAudioCaptcha
verifyPointCaptcha / verifySimpleClickCaptcha
```

`captcha_click_type` = **terisi** (bukan kosong) → mengindikasikan ada komponen
**KLIK** di samping geser. Tracking: `trackClickSliderCaptchaBackground`,
`trackSliderCaptchaClickRefresh`, `trackVerifySliderCaptcha`.

**Kesimpulan:** puzzle = **bukan slider linear sederhana**. Kombinasi:
- Slot putih (target) di kiri
- Potongan (source) di tengah
- Mekanik bisa **drag ATAU klik**.

## ❌ Gap detection (rule-based) gagal

| Metode | Hasil |
|---|---|
| Variance kolom | inkonsisten (12-64%) |
| Template-match piece | MSE tinggi (6292) — gagal |
| Edge-seam | inkonsisten (13-54%) |
| Warna neutral (celah) | 12.5% (kandidat, tak pasti) |

Celah **ter-camouflage** di gambar; potongan = outline tipis (bukan area warna).

## 📊 Status total (A→W)

| Lapisan | Status |
|---|:-:|
| Endpoint (get_settings_v2, anti_fraud/captcha/*) | ✅ |
| Kripto (AES-128-GCM inline + key-exchange) | ✅ RE |
| Jenis captcha (`advanced_slider`, 5 verify types) | ✅ |
| **Proxy Indonesia** | ✅ (82.158.131.205 ID) |
| **Pipeline otomatis end-to-end** | ✅ |
| — modal bahasa, TOS, submit | ✅ |
| — captcha render + rect presisi | ✅ |
| — human drag + verify endpoint | ✅ |
| Mekanik puzzle dipahami penuh | ❌ |
| Gap detection akurat → lolos | ❌ |

## 🎯 Yang dibutuhkan (2 jalan)

### Jalan 1: nomor fresh + iterasi mekanik
Dengan **1 nomor fresh** (proxy ID), uji 3 hipotesis mekanik:
- klik slot putih → verify?
- drag grip horizontal → verify?
- drag potongan → slot → verify?

Lihat mana yang **lolos** (bukan captcha refresh).

### Jalan 2: gameplay manual
Rekam/screenshot saat **geser manual** → lihat apa yang bergerak & bagaimana.
Ini mengungkap mekanik tanpa menebak.

## Infrastruktur: SIAP

`solve_one.py` + `tools/gap_v2.py` + `tools/ui_solver.py` + hook lengkap.
Begitu mekanik dipahami → solver tinggal disesuaikan → otomatis sampai OTP.
