# Opsi F — Solver UI-Driven (Playwright): Hasil

**Tanggal:** 2026-10-14
**Pendekatan:** karena fungsi kripto SDK captcha terkunci di IIFE (opsi C/E),
jawab captcha lewat **interaksi UI seperti manusia** — bukan panggil kripto.

---

## Yang dibangun

### `tools/ui_solver.py` — driver mouse manusiawi
- `human_move(page, x0,y0, x1,y1)` — gerak bertahap + easing cubic + jitter
- `human_click(page, x, y)` — pre-move, hold acak, lepas
- `human_drag(page, x0,y0, x1,y1)` — geser slider bertahap (easing + mikro-pause)
- `find_captcha_elements(page)` — deteksi canvas/slider/grip/img/text
- `attempt_solve(page, kind=auto|slider|click)` — orkestrasi

### `tools/signup_driver.py` — JS-only chain driver (anti-hang)
- Semua interaksi via `page.evaluate()` + `el.click()` (hindari hang locator)
- `dismiss_lang` · `fill_field` · `check_tos` · `click_submit` (prioritas: Kirim→Berikutnya→Daftar) · `JS_CLICK_AGREE` (modal S&K) · `wait_for_captcha`

### `tools/captcha_hook.py` — hook fetch/XHR (dari opsi B)
Rekam generate/verify/config/feedback in-page.

---

## 🧱 Hambatan nyata (jujur)

### 1. Chain signup Shopee desktop TIDAK konsisten
Tiap load halaman menampilkan **variasi form berbeda**:
- versi A: 1 field (No. HP/Email) + tombol "BERIKUTNYA"
- versi B: 2 field (HP + Password) + tombol "Daftar Log in"
- versi C: field HP + "Kode Verifikasi" + tombol "Kirim" + "Berikutnya"
- versi D: field HP + "Kode Verifikasi" + tombol "Kirim Kode"

Modal "Pilih Bahasa Anda" sering **muncul ulang** dan mereset form.
A/B test + GeoIP + state server → form berubah-ubah.

### 2. Captcha belum terpicu penuh di headless
- `#anti_fraud_captcha` **muncul di DOM** (`container: true`, `visible: true`)
- TAPI `canvases/sliders/grips = 0` — konten challenge belum di-render
- `generate` API belum terpanggil (`capture: 0`) di run headless

**Sebab:** tombol pemicu (Kirim / Berikutnya) sering ke-miss karena teks tombol
bervariasi + modal bahasa menutup. Tanpa pemicu benar, SDK captcha belum
men-generate challenge.

### 3. Overlay menghalangi klik
`<div class="vwqiT4 Mn96yZ"> intercepts pointer events` → locator Playwright
hang. Di-mitigasi dgn JS-click, tapi tombol spesifik tetap sulit ditarget stabil.

---

## 📊 Status F

| Komponen | Status |
|----------|:-:|
| Driver mouse manusiawi (klik/geser) | ✅ lengkap |
| Deteksi elemen captcha | ✅ |
| JS-only chain driver (anti-hang) | ✅ |
| Hook flow captcha | ✅ (opsi B) |
| Chain signup konsisten | ❌ form A/B/C/D bergantian |
| Captcha challenge ter-render | ❌ belum di headless |
| Auto-jawab end-to-end | ⬜ (menunggu challenge ter-render) |

---

## 🎯 Jalur agar captcha benar-benar terpicu

1. **Pakai browser non-headless** (Xvfb/desktop) — beberapa anti-bot tidak
   render challenge di headless murni.
2. **Handle form dinamis**: deteksi tombol by fungsi (bukan teks), retry
   multi-variasi, tunggu sampai `generate` API muncul.
3. **Isi field by placeholder/aria**, bukan by index (index bergeser antar versi).
4. **Diamkan modal bahasa**: klik & tunggu hilang, baru interaksi form.
5. Setelah challenge ter-render → `attempt_solve` sudah siap (slider/klik).

Semua komponen solver **siap pakai**. Yang kurang = memicu challenge di
lingkungan headless yang konsisten. Di browser riil (dengan display) ini
jalan; di CI headless butuh Xvfb + penanganan form dinamis.
