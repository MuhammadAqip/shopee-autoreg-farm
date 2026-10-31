# TROUBLESHOOTING — Gejala → Penyebab → Fix

Referensi cepat untuk masalah yang sudah pernah dialami. Kalau gejalanya
tidak ada di sini, cek `project/*.md` — 50 file riset sering menyimpan
jawabannya.

---

## Captcha

### Puzzle tidak muncul

**Gejala**

```
#anti_fraud_captcha tetap <div></div> kosong
menunggu 20 detik, tidak ada canvas
```

**Penyebab**

Puzzle hanya render ~1 dari 3 percobaan. Bukan bug kita.

**Fix**

```python
if not wait_captcha(page, timeout=20):
    page.reload(wait_until="load")
    time.sleep(3)
    # ulangi, jangan submit
```

Jangan submit tanpa captcha — itu menaikkan risk score.

---

### SadCaptcha 400

**Gejala**

```json
{"error": "..."}  HTTP 400
```

**Penyebab (urut kemungkinan)**

1. Body tidak punya `slide_piece_trajectory`
2. Trajectory kurang dari 12 baris
3. `puzzle_image_b64` kosong atau bukan base64 valid
4. `licenseKey` dikirim lewat header, bukan query param

**Fix**

```python
assert len(traj) >= 12, f"traj hanya {len(traj)} baris"
assert puzzle_b64, "puzzle kosong"
requests.post(url, params={"licenseKey": key}, json=body)   # params, bukan headers
```

---

### SadCaptcha 401 / 403

**Penyebab**

Kredit habis atau key mati.

**Fix**

```bash
python3 key_manager.py refresh
python3 key_manager.py status
```

Kalau semua dead, tambah key:

```bash
python3 key_manager.py add <license_key>
```

Failover otomatis hanya mencoba 3 key. Kalau 10 key terdaftar tapi cuma 1
hidup, failover bisa gagal.

---

### Solver mengembalikan pixely salah terus

**Gejala**

```
pixelsFromSliderOrigin: 42   ← padahal celah di ~140
verify gagal berulang
```

**Penyebab**

- `pre-analyze` mengembalikan `skipRecommended: true` tapi diabaikan
- `slideXProportion >= 0.99` (puzzle jelek)
- Trajectory tidak mencerminkan gerakan asli (array buatan)

**Fix**

```python
pre = pre_analyze(puzzle_b64, key)
if pre.get("skipRecommended") or pre.get("slideXProportion", 0) >= 0.99:
    refresh_captcha(page)
    continue        # jangan solve
```

---

### `toDataURL` raise SecurityError

**Penyebab**

Canvas tainted oleh gambar cross-origin. Browser memblokir export.

**Fix**

Ambil screenshot region sebagai ganti:

```python
box = page.locator(selector).first.bounding_box()
png = page.screenshot(clip=box)
b64 = base64.b64encode(png).decode()
```

Screenshot tidak tainted. Kualitas cukup untuk solver.

---

### Captcha verify lolos tapi OTP tidak terkirim

**Penyebab**

Token captcha kedaluwarsa (biasanya < 60 detik setelah solve).

**Fix**

Segera kirim `send_otp` setelah solve. Jangan lakukan hal lain di antaranya.

---

## Registrasi

### `get_settings_v2` → `error: -1`

**Penyebab**

Format nomor salah. Server tidak bisa parse.

**Fix**

```python
def normalize(phone):
    p = phone.replace("+", "").replace(" ", "").replace("-", "")
    if p.startswith("0"):
        p = "62" + p[1:]
    return p

"081234567890"  → "6281234567890"   ✅
```

---

### `error: 4108` — anti-fraud

**Penyebab**

Rule engine menandai device/IP/nomor.

**Fix**

- Ganti proxy (harus residential)
- Ganti nomor
- Tunggu beberapa jam
- **Jangan** retry dari IP yang sama

---

### "Identifikasi Tambahan"

**Gejala**

```
modal muncul setelah OTP
"Identifikasi Tambahan"
```

**Ini bukan error.** Nomor ditandai Shopee.

**Fix**

```python
result = classify(...)
# status = "limit"
# catat ke reputasi, skip nomor
# JANGAN retry
```

Retry di gate ini = 1 kredit hangus + flag IP naik.

---

### Field nomor tidak ditemukan

**Penyebab**

Halaman belum selesai render React.

**Fix**

```python
page.goto(url, wait_until="load", timeout=60000)
time.sleep(5)
# baru query
page.locator("input[type='tel']").first.fill(phone)
```

`domcontentloaded` tidak cukup untuk halaman Shopee.

---

### Modal "Simak Ketentuan" tidak muncul

**Penyebab**

TOS belum diceklis, atau klik "Berikutnya" tidak terdaftar.

**Fix**

```python
page.locator("input[type='checkbox']").first.check(force=True)
time.sleep(0.5)
page.locator("button:has-text('Berikutnya')").first.click(force=True)
time.sleep(2)
```

---

### Klik gagal karena overlay

**Gejala**

```
<div class="GIv4S4"></div> from <div id="modal">…</div>
subtree intercepts pointer events
```

**Fix**

```python
page.locator(selector).first.click(force=True)
# atau
page.locator(selector).first.click(force=True, timeout=10000)
```

Kalau masih gagal, pakai JS click:

```python
page.evaluate("(s) => document.querySelector(s).click()", selector)
```

---

## Cache

### Cache tidak pernah hit

**Penyebab**

Primary key salah — memakai hash `sha256(puzzle + piece)`.

`piece` berbeda tiap render walau puzzle sama.

**Fix**

```sql
PRIMARY KEY (puzzle_b64)   -- content match, bukan hash
```

Cek:

```bash
python3 -c "
import sqlite3
db = sqlite3.connect('captcha_cache.db')
print(db.execute('SELECT sql FROM sqlite_master WHERE name=\"cache\"').fetchone()[0])
"
```

Kalau masih `hash`, migrasi diperlukan.

---

### DB tumbuh cepat

**Gejala**

```
24 MB untuk 161 puzzle  (~150 KB/puzzle)
```

**Fix**

```bash
python3 captcha_cache.py prune 30
python3 captcha_cache.py vacuum
```

Kalau perlu lebih agresif, buang entry yang `hits == 0` dan umur > 7 hari.

---

### Cache hit tapi jawaban salah

**Penyebab**

Puzzle mirip tapi bukan identik. Content match pada base64 memang persis,
tapi kalau `puzzle_b64` di-crop beda (misal screenshot vs canvas), hasilnya
bisa mirip tapi beda.

**Fix**

Pastikan puzzle yang disimpan dan dicari berasal dari sumber yang sama
(canvas `toDataURL`, bukan screenshot).

---

## Browser & Playwright

### Browser crash / RAM penuh

**Gejala**

```
Target page, context or browser has been closed
```

**Fix**

```bash
free -h
pgrep -c chrome
pkill -f "chrome.*headless"; sleep 3
python3 farm_production.py --run --concurrency 1
```

Batas: ~350 MB per browser context. 4 context = 1.4 GB.

---

### `Cannot switch to a different thread`

**Penyebab**

Playwright sync API dipanggil dari thread berbeda.

**Fix**

Semua akses browser di thread yang sama. Kalau memakai thread pool, tiap
thread harus punya browser sendiri, bukan berbagi.

---

### `Playwright Sync API inside the asyncio loop`

**Penyebab**

Driver sudah setengah mati (biasanya setelah `close()` dari thread salah).
Pesan errornya menyesatkan — bukan soal asyncio.

**Fix**

Restart proses. Tidak ada cara memulihkan driver yang sudah rusak.

---

### Headless gagal, non-headless jalan

**Penyebab**

Sebagian halaman Shopee mendeteksi headless.

**Fix**

```bash
xvfb-run -a --server-args="-screen 0 1366x900x24" python3 farm_production.py --run
```

Dan set `HEADLESS=false` di `config.json`.

---

## Proxy

### Semua nomor gagal dengan error jaringan

**Penyebab**

Proxy mati atau credential salah.

**Fix**

```bash
python3 proxy_health.py --verbose
```

Kalau proxy membutuhkan auth, format `proxies.txt` harus:

```
http://user:pass@host:port
```

Kalau HTTPS proxy: `https://user:pass@host:port`.

---

### Satu IP dipakai dua worker

**Gejala**

Dua akun berbeda kena flag bersamaan.

**Fix**

Cek `worker_pool.py` — `proxy_lock` harus aktif. Kalau dimatikan,
hidupkan lagi. Satu proxy hanya boleh satu worker bersamaan.

---

## Key

### Failover tidak jalan

**Penyebab**

`max_keys=3` tapi key hidup < 3.

**Fix**

```bash
python3 key_manager.py status   # berapa alive
```

Tambah key sampai minimal 3 alive.

---

### Kredit cepat habis

**Penyebab**

Cache miss rate tinggi (Shopee rotasi puzzle).

**Fix**

1. Jalankan `prewarm_cache.py` di jam sepi
2. Cek hit rate: `python3 captcha_cache.py stats`
3. Pre-check reputasi supaya tidak menembak nomor yang pasti gagal

---

## OTP

### OTP tidak masuk

**Penyebab**

- Nomor operator lambat
- Channel salah (`1` vs `3`)
- Nomor di-blacklist operator

**Fix**

```python
# coba channel lain dari available_channels
for ch in reversed(available):
    if send_otp(phone, ch) == 0:
        break
```

---

### OTP kedaluwarsa

**Masa berlaku** ~5 menit.

**Fix**

Kalau sink lambat, kirim ulang. Cooldown 60 detik di antara request.

---

## Klasifikasi

### Semua hasil tercatat "ready" padahal banyak limit

**Penyebab**

`classify()` urutan prioritas salah.

**Fix**

```python
if is_limit(text):   return "limit"     # HARUS dicek duluan
if has_userid(d):    return "ready"
return "failed"
```

Kalau `ready` dicek sebelum `limit`, akun yang ditandai tercatat sukses.

---

### Semua tercatat "failed"

**Penyebab**

Field yang dicek untuk `ready` tidak ada. Misal cek `data.user_id` padahal
response mengembalikan `data.userid`.

**Fix**

Cek nama field sebenarnya:

```python
print(json.dumps(resp.get("data"), indent=1))
```

Shopee tidak konsisten: `user_id` vs `userid`, `order_id` vs `order_id_list`.

---

## Diagnostik Umum

### Cek semua sekaligus

```bash
cd project
source /root/sniffenv/bin/activate

python3 key_manager.py status
python3 captcha_cache.py stats
python3 phone_reputation.py stats
python3 proxy_health.py --verbose
python3 health_monitor.py
```

### Kalau mau trace satu akun

```bash
python3 auto_reg.py --mode e2e --phone 081234567890 --verbose 2>&1 | tee debug.log
```

### Kalau perlu screenshot tiap langkah

```python
page.screenshot(path=f"shot_{step}.png", full_page=True)
```

---

## Yang Bukan Bug

Beberapa hal yang kelihatan seperti bug tapi memang perilaku Shopee:

| Gejala | Penjelasan |
|---|---|
| Captcha render 1/3 kali | flaky by design |
| `need_captcha: true` terus | captcha tidak terselesaikan |
| "Identifikasi Tambahan" | nomor ditandai, bukan error kita |
| `error: 98` saat login | password **benar**, butuh IVS |
| `error: 89` saat login API | butuh `shpsec` SDK |
| Puzzle rect tidak bisa dibaca | surface tertutup SDK |
| Cache hit cuma 13% | Shopee rotasi puzzle |
| OTP lambat | operator, bukan sistem |

Sebelum mengubah kode, pastikan gejalanya memang bug, bukan salah satu di
atas.
