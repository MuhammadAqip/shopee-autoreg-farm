# 🎯 SADCAPTCHA API — BREAKTHROUGH (error 400 SOLVED)

## SEBAB ERROR 400 (yang bikin solver gagal)
```
❌ Pakai : POST /shopee-image-crawl  {puzzle, piece}          → 400
✅ Benar : POST /shopee-image-crawl-pre-analyze  {image_b64}  → dulu!
           POST /shopee-image-crawl  {puzzle, piece, slide_piece_trajectory}  → 200
```
**Body WAJIB ada `slide_piece_trajectory` (array, >=12 rows).** Kita kemarin kirim cuma
puzzle+piece → 400.

## ENDPOINT RESMI (base https://www.sadcaptcha.com/api/v1)
```
GET  /license/credits?licenseKey=X              → {"credits": N}
POST /shopee-image-crawl-pre-analyze?licenseKey=X
       body {"image_b64": puzzle}
       → {version, slideXProportion, skipRecommended}
POST /shopee-image-crawl?licenseKey=X
       body {puzzle_image_b64, piece_image_b64, slide_piece_trajectory[]}
       → {"pixelsFromSliderOrigin": N}
POST /puzzle  {puzzleImageB64, pieceImageB64}   → {"slideXProportion": f}
POST /shopee-image-drag
```
- licenseKey = **QUERY PARAM** (bukan header!)
- body image-crawl = **snake_case**; endpoint lain **camelCase**

## TRAJECTORY ROW FORMAT
```json
{
  "pixels_from_slider_origin": 137,      // int: jarak button dari origin
  "piece_rotation_angle": 12.5,          // float: rotate(Xdeg)
  "piece_center": {"proportionX":0.47, "proportionY":0.62}  // 0..1 (center/container)
}
```

## ALGORITMA (dari script.ts extension)
```
solveImageCrawl:
  1. refresh captcha
  2. ambil puzzle canvas → b64
  3. PRE-ANALYZE → {version, slideXProportion, skipRecommended}
     - skipRecommended   → retry (max 3)
     - slideXProportion≥0.99 → retry (jelek)
  4. ambil piece canvas → b64
  5. RECORD TRAJECTORY:
       mouseDown; sweep 0→0.85*W step 3px;
       SCATTER tiap 30px blok (Fisher-Yates shuffle!);
       sample {pixels, rotation, piece_center};
       stop: piece_center.proportionX >= slideXProportion+15px ATAU diam 10 langkah;
       sort by pixels
  6. POST /shopee-image-crawl {puzzle, piece, trajectory} → solution px
  7. RELEASE manusiawi:
       maxPx = puzzleW*0.85
       toU(px)=px/maxPx*4-2 ; toPx(u)=(u+2)/4*maxPx
       4 oscillation passes (amp 1.5 turun), step 13px; final leg step 15px
       pause 900-2100ms sebelum nudge; 750-1450ms sebelum release
```

## ANTI-BOT CONSTANTS (replikasi di client kita)
```
SCATTER_BLOCK_PX=30    GESTURE_AMP_U=1.5   GESTURE_PASSES=4
GESTURE_PACE_MS=2      SWING_SAFE_PX=12    OVERSHOOT_PX=15
PAUSE_BEFORE_NUDGE_MS=[900,2100]  PAUSE_BEFORE_RELEASE_MS=[750,1450]
MIN_TRAJECTORY_ROWS=12  SKIP_CAP=3   PRESS_SETTLE_MS=150  SAMPLE_SETTLE_MS=20
```

## SELECTOR DOM SHOPEE
```
PUZZLE: "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false], div:not(#puzzleContainer) > img"
PIECE:  "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"
BUTTON: "div:has(> svg + svg)"
```

## STATUS TES
```
✅ /license/credits → 23 credits (API HIDUP)
✅ Endpoint benar (bukan 404 lagi)
✅ Body format ketemu
⚠️ pre-analyze 400 di test cache — butuh image LIVE dari page (bukan cache lama)
   → next: test dengan canvas live dari browser
```

## DELIVERABLE
- `/root/shopee-farm/sadcaptcha_client.py` — client corrected (pre-analyze + trajectory)
- `/root/shopee-farm/sdk/sadcaptcha_ref/` — script.ts, background.ts, manifest, api.py, api-docs.json
- SKILL: `sadcaptcha-shopee-api` (paten: schemas, algorithm, pitfalls, cache-first pattern)

## NEXT (Pure-API target)
1. Integrasi client ke `shopee_hold.py`: ganti solver lama → pre-analyze + trajectory + solve
2. Test dengan captcha LIVE (canvas, bukan cache)
3. Cache-first: kalau puzzle sudah pernah di-solve → pakai cache (gratis)
4. Pure-API: karena trajectory butuh browser untuk record → minimal browser (canvas + mouse events)
   sisanya (solve) full API. Page-context fetch (Option A) tetap untuk signing.
