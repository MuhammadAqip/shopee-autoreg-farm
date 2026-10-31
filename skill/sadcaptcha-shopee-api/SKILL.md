---
name: sadcaptcha-shopee-api
description: "Use for SadCaptcha Shopee captcha solver API calls."
version: 1.0.0
---

# SadCaptcha Shopee Captcha Solver — API Reference

Base URL: `https://www.sadcaptcha.com/api/v1`

**Auth:** `licenseKey` is a **QUERY PARAMETER** on every endpoint (not a header).
Example: `https://www.sadcaptcha.com/api/v1/shopee-image-crawl?licenseKey=YOUR_KEY`

**Headers:** `Content-Type: application/json`

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/license/credits` | Check credits: `{"credits": N}` |
| POST | `/shopee-image-crawl-pre-analyze` | Analyze puzzle image BEFORE solving |
| POST | `/shopee-image-crawl` | Solve arced-slide challenge (needs trajectory) |
| POST | `/puzzle` | Simple slide-puzzle (2-image) |
| POST | `/shopee-image-drag` | Drag missing piece then click Verify |
| POST | `/semantic-shapes` | Text-challenge shapes |

## /shopee-image-crawl — THE RULE THAT FIXES 400

`400 Bad Request` = body incomplete. You MUST send `slide_piece_trajectory`.

Request body (`ImageCrawlCaptchaRequest`):
```json
{
  "puzzle_image_b64": "<base64 PNG>",
  "piece_image_b64": "<base64>",
  "slide_piece_trajectory": [
    {
      "pixels_from_slider_origin": 0,
      "piece_rotation_angle": 0.0,
      "piece_center": {"proportionX": 0.1234, "proportionY": 0.5}
    }
  ]
}
```
- `pixels_from_slider_origin` (int): slider-button distance dragged from origin, per sample.
- `piece_rotation_angle` (float): piece CSS rotate() angle in degrees.
- `piece_center` (proportional point): piece center x/y divided by puzzle container width/height (0..1).
- MIN 12 rows (`MIN_TRAJECTORY_ROWS`).

Response:
```json
{"pixelsFromSliderOrigin": 137}
```

Status codes: `400` = bad request / no answer found - `401` = bad key or out of credits.

## /shopee-image-crawl-pre-analyze — ALWAYS CALL FIRST

Request: `{"image_b64": "<puzzle image b64>"}`
Response:
```json
{"version": "v1", "slideXProportion": 0.4714, "skipRecommended": false}
```
- `skipRecommended: true` -> abandon & refresh this captcha (retry up to 3).
- `slideXProportion >= 0.99` -> captcha malformed, refresh (retry up to 3).
- `slideXProportion` = piece-center-X proportion where motion should STOP during recording.

## DOM SELECTORS (Shopee)

```
PUZZLE_IMAGE: "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false], div:not(#puzzleContainer) > img"
PIECE_IMAGE:  "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"
SLIDER_BTN:   "div:has(> svg + svg)"
RESET_BTN:    "#NEW_CAPTCHA svg[viewBox='0 0 16 16'], aside svg[viewBox='0 0 16 16']"
```

## TRAJECTORY RECORDING ALGORITHM

The piece moves on an ARC, not linear. To record:
1. `mouseDown` on slider button center.
2. Sweep x from 0 -> `0.85 * puzzleWidth`, step 3px.
3. SCATTER each 30px block: shuffled pixel order (Fisher-Yates) - random order defeats bot detection; do NOT sweep monotonically.
4. After each move sample: `pixels_from_slider_origin` (button x - origin), `piece_rotation_angle` (parse `rotate(Xdeg)` from piece inline style), `piece_center` (piece rect center as proportion of puzzle box).
5. STOP when `piece_center.proportionX >= slideXProportion` AND overshoot >= 15px; OR piece not moved for 10 samples.
6. Sort by `pixels_from_slider_origin` before sending.

## HUMAN-LIKE RELEASE (post-solution)

```
maxPx = puzzleWidth * 0.85
toU(px) = px/maxPx*4 - 2
toPx(u) = (u+2)/4*maxPx
aimU = toU(solution)
# 4 oscillation passes (decreasing amplitude 1.5), step 13px; final leg step 15px to solution
# pause random 900-2100ms before nudge, 750-1450ms before release
```
Gesture constants: `GESTURE_AMP_U=1.5`, `GESTURE_PASSES=4`, `GESTURE_PACE_MS=2`,
`PAUSE_BEFORE_NUDGE_MS=[900,2100]`, `PAUSE_BEFORE_RELEASE_MS=[750,1450]`,
`OVERSHOOT_PX=15`, `SWING_SAFE_PX=12`, `SCATTER_BLOCK_PX=30`, `SKIP_CAP=3`.

## SIMPLE PYTHON CLIENT

```python
import requests
BASE = "https://www.sadcaptcha.com/api/v1"

def credits(key):
    return requests.get(f"{BASE}/license/credits", params={"licenseKey": key}).json()["credits"]

def pre_analyze(key, image_b64):
    r = requests.post(f"{BASE}/shopee-image-crawl-pre-analyze",
                      params={"licenseKey": key}, json={"image_b64": image_b64})
    return r.json()   # {version, slideXProportion, skipRecommended}

def solve_image_crawl(key, puzzle_b64, piece_b64, trajectory):
    r = requests.post(f"{BASE}/shopee-image-crawl", params={"licenseKey": key}, json={
        "puzzle_image_b64": puzzle_b64,
        "piece_image_b64": piece_b64,
        "slide_piece_trajectory": trajectory,
    })
    if r.status_code == 400: raise RuntimeError("bad request / no answer")
    if r.status_code == 401: raise RuntimeError("bad key or out of credits")
    return r.json()["pixelsFromSliderOrigin"]

def solve_puzzle(key, puzzle_b64, piece_b64):
    r = requests.post(f"{BASE}/puzzle", params={"licenseKey": key},
                      json={"puzzleImageB64": puzzle_b64, "pieceImageB64": piece_b64})
    return r.json()["slideXProportion"]   # camelCase here
```

Field-name gotcha: camelCase everywhere else (`puzzleImageB64`, `pixelsFromSliderOrigin`, `slideXProportion`, `proportionX`) EXCEPT the image-crawl request body which uses snake_case.

## REPOS
- `github.com/gbiz123/shopee-captcha-solver` (PyPI `shopee-captcha-solver`) - Selenium/Playwright/Nodriver clients
- `github.com/gbiz123/shopee-captcha-solver-chrome-extension` - MV3 extension, `script.ts` = reference solver
- `github.com/gbiz123/sadcaptcha-code-examples` - puzzle/rotate/shapes examples
- Swagger: https://www.sadcaptcha.com/api/v1/swagger-ui/index.html - OpenAPI JSON: https://www.sadcaptcha.com/api/v1/v3/api-docs

## PATTERN: CACHE-FIRST + API FALLBACK

Resolve captcha cache-first (match exact puzzle bytes in local SQLite; store solved `pixelsFromSliderOrigin`/proportion). Call the API only on MISS. Prewarm when credits available; serve from cache in production to save credits.
- Cache lookup MUST use content match (b64 bytes), not a stored hash.
- Use SQLite WAL mode to avoid 'database is locked' with a concurrent prewarm writer.

## PITFALLS
- `400` almost always = missing/too-short `slide_piece_trajectory` (>=12 rows) OR wrong field casing.
- `401` = bad key OR out of credits - check `/license/credits` first.
- The Shopee arced-slide has TWO plausible landing spots; the API disambiguates using the trajectory - do NOT solve with a single gap-detection/OpenCV template match; accuracy is low.
- `slideXProportion` is a PROPORTION (0..1) of container width, not pixels.
