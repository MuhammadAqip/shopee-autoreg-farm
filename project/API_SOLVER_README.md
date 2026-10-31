# Shopee Auto-Register — API-Only Solver (Bot-Ready)

**Deliverable buat Maker.** Solver mandiri pakai SadCaptcha REST API. **Nggak butuh Chrome extension** — cocok headless/bot.

## File

| File | Fungsi |
|---|---|
| `shopee_solver.py` | **Solver utama (API-only).** Alur lengkap: signup → captcha → OTP modal |
| `solve_official.py` | Referensi: solver via extension (bukti captcha bisa lolos) |

## Cara pakai

```bash
cd /root/shopee-farm
xvfb-run -a --server-args="-screen 0 1280x900x24" \
  /root/sniffenv/bin/python shopee_solver.py <NOMOR> <SADCAPTCHA_KEY> [PROXY_PORT]
```

Contoh:
```bash
xvfb-run -a /root/sniffenv/bin/python shopee_solver.py 087876125616 2471... 10000
```

Env override (buat bot):
- `SHOPEE_PROXY` / `SHOPEE_PROXY_USER` / `SHOPEE_PROXY_PASS`
- `SADCAPTCHA_KEY`, `PHONE`, `SHOPEE_PROXY_PORT`

Output JSON: `{"phone":..., "stage":"otp_modal_sent|otp|error|CAPTCHA", "attempts":N}`

## Alur

1. Buka `shopee.co.id/buyer/signup` + proxy ID
2. Dismiss modal bahasa → fill nomor → submit "BERIKUTNYA"
3. Modal TOS "Simak Ketentuan Akun" → klik "Setuju"
4. **CAPTCHA (canvas):**
   - `canvas.EkGpDI` (puzzle 280×150) → `toDataURL()` → B64
   - `canvas._0N0-Dn` (piece 44×44) → B64
   - `POST /puzzle?licenseKey=KEY` → `slideXProportion`
   - **drag distance = puzzle_width × prop** (pola ekstensi)
   - max 6 attempt
5. Modal OTP WhatsApp → klik "Kirim ke WhatsApp"
6. Tunggu field OTP

## Mekanik drag (PENTING — pola ekstensi SadCaptcha)

`script.js` ekstensi (fungsi `solvePuzzle`):

```js
sleep(3000)
mouseEnterPage()             // natural approach
mouseMove(center); down(center)
// prep-drag 10px:
for i in 1..10:
    x = center.x + i
    y = center.y - Math.log(i) + rand()*3
    mouseMove(x, y)
puzzle/piece -> API -> solution
distance = puzzleWidth * solution     // <-- FULL WIDTH × prop (BUKAN track - grip!)
i = 1
while i < distance - 10:
    x = center.x + i + 10
    y = center.y - Math.log(i) + rand()*3
    mouseMove(x, y); sleep(rand()*5 + 10)
sleep(133.7)
mouseMove(center.x + distance, center.y)
sleep(133.7)
mouseUp(center.x + distance, center.y)
```

**3 hal krusial:**
1. `distance = puzzleWidth × prop` (280 × prop) — **jangan** kurangi grip width
2. `y = center.y − log(i)` (naik melengkung natural)
3. Prep-drag 10px SEBELUM extract puzzle (buka state drag)

## Selector (Shopee ID — CANVAS, bukan img)

| Elemen | Selector |
|---|---|
| Puzzle | `aside[aria-modal=true] canvas.EkGpDI` (280×150) |
| Piece | `aside[aria-modal=true] canvas._0N0-Dn` (44×44) |
| Grip | `aside[aria-modal=true] div.dExCsf` (40×40) |
| Track | `aside[aria-modal=true] div.FVDNdI` (280) |
| Instruction | `div._9s-sAH` = "Geser untuk menyelesaikan puzzle" |
| Modal | `aside[aria-modal=true].NBe1If` |

**Kenapa canvas penting:** Shopee ID render puzzle/piece sebagai `<canvas>`, BUKAN `<img>`. SadCaptcha selector resmi (`img[draggable]`) nggak match → harus `canvas.toDataURL()`.

## SadCaptcha API

- Base: `https://www.sadcaptcha.com/api/v1/`
- `POST /puzzle` body `{puzzleImageB64, pieceImageB64}` → `{slideXProportion}` (0-1)
- `POST /shopee-image-drag` (alias `/puzzle`)
- `POST /shopee-image-crawl` body `{puzzle_image_b64, piece_image_b64, slide_piece_trajectory}` → `{pixelsFromSliderOrigin}`
- Credits: `GET /license/credits?licenseKey=KEY`
- Harga ~$0.0020/solve

## Status (terbukti)

- ✅ **Captcha BISA lolos** (extension solve → OTP modal WhatsApp muncul 2× pada run 10005 / 10002).
- ✅ API-only solver = pola persis ekstensi.
- ⚠️ **Limit ~5-6 attempt per nomor** → "Verifikasi gagal. Coba lagi beberapa menit lagi."
- ⚠️ Nomor bekas banyak attempt → stuck language modal (rate-flagged).

## Buat bot

```python
import subprocess, json
r = subprocess.run(
    ["xvfb-run", "-a", "/root/sniffenv/bin/python",
     "/root/shopee-farm/shopee_solver.py", phone, SADCAPTCHA_KEY, str(port)],
    capture_output=True, text=True, timeout=300)
res = json.loads(r.stdout.strip().splitlines()[-1])
# res["stage"] == "otp_modal_sent" -> tunggu OTP SMS/WA
```

Atau import langsung `solve_captcha(page)` setelah halaman di posisi captcha.
