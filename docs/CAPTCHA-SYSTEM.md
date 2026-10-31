# CAPTCHA SYSTEM — Protokol Lengkap

Referensi teknis sistem captcha: jenis, protokol API, rekaman trajectory,
release manusiawi, cache, dan konstanta anti-bot.

---

## 1. Tiga Jenis Captcha

| Konteks | Jenis | Penanganan | Kesulitan |
|---|---|---|---|
| Signup desktop | reCAPTCHA v2 | solver pihak ketiga | mudah |
| OTP mobile | Slider geetest | solver slider | sedang |
| `anti_fraud` (image crawl) | Puzzle geser | SadCaptcha API | sulit |

Ketiganya bisa muncul di alur yang sama. Urutan penanganan tergantung
`captcha_scene` dari `get_settings_v2`.

---

## 2. Deteksi Jenis

```python
def detect_captcha_type(page):
    if page.locator("iframe[src*='recaptcha']").count():
        return "recaptcha_v2"

    if page.locator(".geetest_slider, .geetest_panel").count():
        return "geetest_slider"

    if page.locator("#anti_fraud_captcha, #NEW_CAPTCHA").count():
        return "image_crawl"

    return None
```

Selector harus diperbarui kalau Shopee ubah markup. Kalau semua gagal,
pakai tangkapan layar untuk menentukan jenisnya secara visual.

---

## 3. SadCaptcha — Protokol Lengkap

### Base & auth

```
base URL : https://www.sadcaptcha.com/api/v1
auth     : ?licenseKey=X   ← QUERY PARAM, bukan header
```

Kalau key dikirim sebagai header, semua endpoint balik `401`.

### Endpoint

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/license/credits` | — | `{"credits": N}` |
| POST | `/shopee-image-crawl-pre-analyze` | `{"image_b64": str}` | `{version, slideXProportion, skipRecommended}` |
| POST | `/shopee-image-crawl` | `{puzzle_image_b64, piece_image_b64, slide_piece_trajectory[]}` | `{"pixelsFromSliderOrigin": N}` |
| POST | `/puzzle` | `{puzzleImageB64, pieceImageB64}` | `{"slideXProportion": f}` |
| POST | `/shopee-image-drag` | `{...}` | `{...}` |

**Perhatikan casing:** body `image-crawl` = **snake_case**; endpoint lain =
**camelCase**. Ini inkonsistensi API asli, bukan bug.

### Contoh lengkap

```python
import requests, base64

BASE = "https://www.sadcaptcha.com/api/v1"

def credits(key):
    r = requests.get(f"{BASE}/license/credits",
                     params={"licenseKey": key})
    return r.json()["credits"]

def pre_analyze(puzzle_b64, key):
    r = requests.post(f"{BASE}/shopee-image-crawl-pre-analyze",
                      params={"licenseKey": key},
                      json={"image_b64": puzzle_b64})
    return r.json()

def solve(puzzle_b64, piece_b64, trajectory, key):
    r = requests.post(f"{BASE}/shopee-image-crawl",
                      params={"licenseKey": key},
                      json={
                        "puzzle_image_b64": puzzle_b64,
                        "piece_image_b64": piece_b64,
                        "slide_piece_trajectory": trajectory,
                      })
    return r.json()["pixelsFromSliderOrigin"]
```

---

## 4. Error yang Sering Muncul

| Gejala | Penyebab | Fix |
|---|---|---|
| `400` | body tanpa `slide_piece_trajectory` | tambahkan, min 12 baris |
| `400` | trajectory < 12 baris | rekam lebih jauh |
| `400` | `puzzle_image_b64` kosong / bukan b64 | ekstrak ulang dari canvas |
| `401` | key tidak dikirim sebagai query param | pakai `params=`, bukan `headers=` |
| `401` | kredit habis | `key_manager.refresh()` |
| `skipRecommended: true` | kualitas puzzle jelek | refresh captcha, retry (maks 3) |
| `slideXProportion >= 0.99` | jawaban tidak berguna | refresh captcha |

---

## 5. Ekstraksi Gambar dari Halaman

Puzzle dan piece tidak bisa diambil lewat DOM query biasa (surface tertutup
untuk geometri), **tapi canvas-nya bisa di-serialize** kalau selector tepat.

```python
PUZZLE_SEL = ("#NEW_CAPTCHA canvas[draggable=false], "
              "aside canvas[draggable=false], "
              "div:not(#puzzleContainer) > img")

PIECE_SEL  = ("#NEW_CAPTCHA canvas[draggable=true], "
              "aside canvas[draggable=true], "
              "#puzzleContainer > #puzzleImgComponent")

def grab_b64(page, selector):
    return page.evaluate("""(sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;

        if (el.tagName === 'CANVAS') {
            return el.toDataURL('image/png').split(',')[1];
        }
        if (el.tagName === 'IMG') {
            const c = document.createElement('canvas');
            c.width = el.naturalWidth;
            c.height = el.naturalHeight;
            c.getContext('2d').drawImage(el, 0, 0);
            return c.toDataURL('image/png').split(',')[1];
        }
        return null;
    }""", selector)
```

**Penting:** kalau canvas `tainted` (gambar cross-origin), `toDataURL` akan
raise `SecurityError`. Dalam kasus itu, ambil screenshot region:

```python
def grab_screenshot_region(page, selector):
    box = page.locator(selector).first.bounding_box()
    return page.screenshot(clip=box)
```

---

## 6. Rekaman Trajectory

Ini bagian paling kritis. Tanpa trajectory asli, API menolak.

### Kenapa harus asli

`pre-analyze` menganalisis gerakan awal untuk menentukan apakah request datang
dari manusia. Array buatan dengan nilai acak akan gagal konsistensi.

Yang harus ada per baris:

```
pixels_from_slider_origin : int, monoton naik setelah sort
piece_rotation_angle      : float, berubah saat geser
piece_center              : {proportionX, proportionY}, 0..1
```

### Implementasi

```python
def record_trajectory(page, piece_box, puzzle_width, slide_x_prop):
    traj = []
    px, py = piece_box["x"] + piece_box["width"] / 2, \
             piece_box["y"] + piece_box["height"] / 2

    page.mouse.move(px, py)
    page.mouse.down()
    time.sleep(0.15)                       # PRESS_SETTLE_MS

    step = 3
    block_size = 30 // step                # tiap 30 px
    block = []
    x = 0
    stalled = 0
    prev_prop = 0

    max_x = puzzle_width * 0.85

    while x <= max_x:
        page.mouse.move(px + x, py)
        time.sleep(0.002)                  # SAMPLE_SETTLE_MS

        prop = x / puzzle_width
        rot = piece_rotation(page)         # dari transform CSS

        block.append({
            "pixels_from_slider_origin": x,
            "piece_rotation_angle": rot,
            "piece_center": {
                "proportionX": prop,
                "proportionY": 0.5,
            },
        })

        # scatter tiap blok (Fisher-Yates)
        if len(block) >= block_size:
            random.shuffle(block)
            traj.extend(block)
            block = []

        # stop conditions
        if prop >= slide_x_prop + 15 / puzzle_width:
            break
        if prop == prev_prop:
            stalled += 1
            if stalled >= 10:
                break
        else:
            stalled = 0
        prev_prop = prop

        x += step

    if block:
        traj.extend(block)

    traj.sort(key=lambda r: r["pixels_from_slider_origin"])
    return traj
```

### Validasi sebelum kirim

```python
assert len(traj) >= 12, "trajectory terlalu pendek"
assert all("pixels_from_slider_origin" in r for r in traj)
assert traj == sorted(traj, key=lambda r: r["pixels_from_slider_origin"])
```

---

## 7. Release Manusiawi

Setelah `target_px` didapat, geser dengan pola manusia.

```python
import random, time

def release(page, y, target_px, puzzle_width):
    max_px = puzzle_width * 0.85
    to_u = lambda px: px / max_px * 4 - 2
    to_px = lambda u: (u + 2) / 4 * max_px

    # 4 oscillation pass, amplitudo turun
    passes = 4
    for i in range(passes):
        amp = 1.5 - i * 0.3
        for k in range(4):
            u = to_u(target_px) + amp * (1 if k % 2 == 0 else -1)
            page.mouse.move(to_px(u), y)
            time.sleep(0.002)

    # final leg
    cur = target_px - 30
    step = 15
    while abs(cur - target_px) > step:
        cur += step if target_px > cur else -step
        page.mouse.move(cur, y)
        time.sleep(0.002)

    # pause sebelum release
    time.sleep(random.uniform(0.75, 1.45))
    page.mouse.up()
```

Pause sebelum release itu wajib. Tanpa itu, verifikasi sering menolak karena
gerakan terlihat terlalu mekanis.

---

## 8. Konstanta Anti-Bot

Nilai ini direplikasi dari referensi SDK dan harus dijaga:

```python
SCATTER_BLOCK_PX        = 30
GESTURE_AMP_U           = 1.5
GESTURE_PASSES          = 4
GESTURE_PACE_MS         = 2
SWING_SAFE_PX           = 12
OVERSHOOT_PX            = 15
PAUSE_BEFORE_NUDGE_MS   = (900, 2100)
PAUSE_BEFORE_RELEASE_MS = (750, 1450)
MIN_TRAJECTORY_ROWS     = 12
SKIP_CAP                = 3
PRESS_SETTLE_MS         = 150
SAMPLE_SETTLE_MS        = 20
```

Mengubah tanpa kalibrasi ulang → captcha ditolak lebih sering.

---

## 9. Cache

### Skema

```sql
CREATE TABLE cache (
  puzzle_b64 TEXT PRIMARY KEY,
  answer_x   INTEGER NOT NULL,
  hits       INTEGER DEFAULT 0,
  verified   INTEGER DEFAULT 0,
  created_at INTEGER
);
PRAGMA journal_mode = WAL;
```

### Operasi

```python
class Cache:
    def get(self, puzzle_b64):        ...
    def put(self, puzzle_b64, ans):   ...
    def stats(self):                  ...
    def prune(self, max_age_days):    ...
```

### Mengapa `puzzle_b64` sebagai key

Versi lama memakai `sha256(puzzle + piece)`. `piece` berbeda tiap render walau
puzzle sama, sehingga **selalu MISS**. Content match mengabaikan piece.

Panjang `puzzle_b64` bisa 100–200 KB. SQLite menangani ini dengan baik selama
`TEXT` bukan `BLOB` dan query memakai equality index.

### Angka

```
161 puzzle · 21 pernah hit (13%) · 24 hit total · 24 MB
```

---

## 10. Integrasi dengan Chain

```python
def solve_captcha(page, key):
    puzzle = grab_b64(page, PUZZLE_SEL)
    piece  = grab_b64(page, PIECE_SEL)

    # L1: cache
    hit = cache.get(puzzle)
    if hit is not None:
        return hit

    # L2: API
    for attempt in range(SKIP_CAP):
        pre = pre_analyze(puzzle, key)

        if pre.get("skipRecommended"):
            refresh_captcha(page)
            puzzle = grab_b64(page, PUZZLE_SEL)
            continue

        if pre.get("slideXProportion", 0) >= 0.99:
            refresh_captcha(page)
            continue

        traj = record_trajectory(page, piece_box, puzzle_w, pre["slideXProportion"])
        ans  = solve(puzzle, piece, traj, key)

        cache.put(puzzle, ans)
        return ans

    raise RuntimeError("captcha gagal setelah 3 percobaan")
```

---

## 11. Captcha Flaky

Di data produksi, puzzle hanya render ~1 dari 3 percobaan.
Gejala: `#anti_fraud_captcha` tetap kosong setelah 10 detik.

Penanganan:

```python
def wait_captcha(page, timeout=20):
    for _ in range(timeout):
        if page.locator(PUZZLE_SEL).count():
            return True
        time.sleep(1)
    return False
```

Kalau gagal setelah timeout → refresh halaman, bukan retry submit. Retry
submit di captcha yang tidak render akan menaikkan risk score.

---

## 12. Ringkasan Alur

```
captcha muncul
  ├─ deteksi jenis
  │    ├─ recaptcha  → solver pihak ketiga
  │    ├─ geetest    → solver slider
  │    └─ image crawl → alur di bawah
  │
  ├─ tunggu render (maks 20 s)
  │    └─ gagal → refresh halaman
  │
  ├─ grab puzzle + piece → b64
  ├─ cache lookup
  │    ├─ HIT  → answer, selesai (0 kredit)
  │    └─ MISS ↓
  │
  ├─ pre-analyze
  │    ├─ skipRecommended      → refresh, ulangi (maks 3)
  │    └─ slideXProportion≥.99 → refresh, ulangi
  │
  ├─ rekam trajectory (browser, event mouse asli)
  ├─ solve API  → target_px
  ├─ cache.put
  └─ release manusiawi → verify
```
