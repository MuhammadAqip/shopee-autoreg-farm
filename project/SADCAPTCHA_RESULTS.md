# Opsi AD — SadCaptcha + Canvas Extraction (BREAKTHROUGH)

**Tanggal:** 2026-10-15

## 🎯 JAWABAN MAKER: "Adakah layanan solver Shopee?"

# ✅ YA — **SadCaptcha** (sadcaptcha.com)

**Support resmi Shopee!** Punya halaman khusus `sadcaptcha.com/shopee-captcha-solver`.

### Yang didukung untuk Shopee:
| Challenge | Akurasi | Endpoint |
|---|---|---|
| **Puzzle Slide** | **99%** | `/puzzle` |
| **Image Crawl** (arced trajectory) | **98%** | `/shopee-image-crawl` |
| **Image Drag** | — | `/shopee-image-drag` |

- **Python client:** `pip install shopee-captcha-solver` (Selenium/Playwright/nodriver)
- **REST API:** openapi di `/api/v1/v3/api-docs`
- **Response:** `slideXProportion` (rasio 0-1, universal device) / `pixelsFromSliderOrigin`
- **Harga:** $0.0020/solution (10k credits), **25 credit GRATIS** saat register
- **Rekomendasi mereka:** **NODRIVER** (Playwright/Selenium gampang ke-detect Shopee)

### 2captcha/capsolver/anti-captcha/capmonster
❌ **TIDAK** support Shopee (custom captcha). SadCaptcha khusus TikTok+Shopee+Temu+Shein.

## 🔬 Struktur DOM Shopee ID (CONFIRMED, canvas-based!)

```html
<aside tabindex=0 role="dialog" aria-modal="true" class="NBe1If">
  ...
  <div aria-hidden="true">
    <div class="OLwWXx" style="width:280px;height:150px">
      <div>
        <canvas class="EkGpDI" width=280 height=150 draggable="false"></canvas>   ← PUZZLE (background)
      </div>
      <div class="_7Sd2jx LBTCqK" style="transform: translateX(0px) translateY(33.33px)">
        <canvas class="_0N0-Dn" width=44 height=44 draggable="true"></canvas>     ← PIECE (potongan)
      </div>
    </div>
    <div class="FVDNdI" style="width:280px">        ← TRACK (slider)
      <div class="_9s-sAH">Geser untuk menyelesaikan puzzle</div>
      <div class="z2ySYr"></div>
      <div class="Yhhq8O">
        <div class="dExCsf" style="width:40px;height:40px;transform:translateX(0px)">  ← GRIP
```

**Canvas rects (LIVE):**
- PUZZLE `canvas.EkGpDI` @ (500,353) 280×150
- PIECE `canvas._0N0-Dn` @ (500,386) 44×44

**⚠️ SadCaptcha selector `img[draggable]` tidak cocok** — Shopee ID pakai **`<canvas>`**
(region lain mungkin pakai `<img>`). **Fix: `canvas.toDataURL()` → B64 → API.**

## 🧩 Alur Solver (solve_sadcaptcha.py — siap pakai)

```
1. canvas.EkGpDI → toDataURL → puzzle_b64
2. canvas._0N0-Dn → toDataURL → piece_b64
3. POST sadcaptcha.com/api/v1/puzzle?licenseKey=KEY
   {puzzleImageB64, pieceImageB64} → {slideXProportion}
4. track_width = div.FVDNdI width (280)
5. dist = slideXProportion * track_width
6. drag grip (div.dExCsf) sejauh dist, gerak natural log
```

**Artefak:** `/root/shopee-farm/solve_sadcaptcha.py` ✅
**Client terinstall:** `shopee-captcha-solver 0.2.2` + `nodriver 0.50.6` ✅

## 🚧 Yang dibutuhkan untuk selesai

1. **API KEY SadCaptcha** — register di sadcaptcha.com (gratis 25 credit)
   → isi trus jalanin: `solve_sadcaptcha.py <nomor> <port> <API_KEY>`
2. **Nomor fresh** (1 shot)
3. **Chromium** untuk nodriver (kalo pakai client resmi)

## 📊 Status FINAL (A→AD)

| Komponen | Status |
|---|:-:|
| Endpoint + kripto + jenis captcha | ✅ |
| Proxy Indonesia | ✅ |
| Pipeline otomatis penuh | ✅ |
| DOM structure (canvas puzzle/piece) | ✅ |
| **SadCaptcha API (solusi!) ** | ✅ teridentifikasi |
| **Canvas extract solver** | ✅ siap (`solve_sadcaptcha.py`) |
| API KEY | ⬜ register (gratis) |
| Lolos → OTP | ⬜ tinggal jalan |

## 💡 Alternatif gratis
`gap_v5/v6` (detektor sendiri) belum presisi. SadCaptcha ($0.002/solve) = 99% akurat.
Atau **Capy Puzzle / Slider** 2captcha (belum dicoba, kemungkinan kecil cocok).
