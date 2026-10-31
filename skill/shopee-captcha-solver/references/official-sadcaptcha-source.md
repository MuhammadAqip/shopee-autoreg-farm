# SadCaptcha Shopee — Sumber Resmi (gbiz123)

Reverse dari 3 repo resmi + swagger. Unggul dari patch lama.

## Repo
- `gbiz123/shopee-captcha-solver` — Python SDK (playwright/selenium/async/nodriver/undetected-chromedriver)
- `gbiz123/shopee-captcha-solver-chrome-extension` — **cara modern resmi** (chrome ext ID `beojaiildognffpjmpiamfofnplkdfih`)
- `gbiz123/sadcaptcha-code-examples` — contoh pemakaian
- Swagger: `https://www.sadcaptcha.com/api/v1/swagger-ui/index.html`, spec `.../v3/api-docs`

## Endpoint API (base `https://www.sadcaptcha.com/api/v1`, auth `?licenseKey=<KEY>`)

| Endpoint | Method | Req | Resp |
|---|---|---|---|
| `/license/credits` | GET | — | `{credits}` |
| `/puzzle` | POST | `{puzzleImageB64, pieceImageB64}` | `{slideXProportion}` |
| `/shopee-image-crawl-pre-analyze` | POST | `{image_b64}` | `{version, slideXProportion, skipRecommended}` |
| `/shopee-image-crawl` | POST | `{puzzle_image_b64, piece_image_b64, slide_piece_trajectory:[{pixels_from_slider_origin, piece_rotation_angle, piece_center:{proportionX,proportionY}}]}` | `{pixelsFromSliderOrigin}` |
| `/shopee-image-drag` | POST | `{puzzleImageB64, pieceImageB64}` | `{proportionalPoints:[{proportionX,proportionY}]}` |
| `/semantic-shapes` | POST | `{image_b64, challenge}` | `{proportionX, proportionY}` |

- HTTP 400 = bad request / answer tak ketemu. HTTP 401 = key salah / kredit habis.
- `slide_piece_trajectory` = minimal **12 baris** (`MIN_TRAJECTORY_ROWS`), sort ascending `pixels_from_slider_origin`.
- `piece_center.proportionX/Y` = center piece / bbox gambar puzzle, **round 4 desimal**.

## Selector RESMI (dari chrome ext, TERBARU)
```js
IMAGE_CRAWL_PUZZLE_IMAGE_SELECTOR = "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false], div:not(#puzzleContainer) > img"
IMAGE_CRAWL_PIECE_IMAGE_SELECTOR  = "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"
IMAGE_CRAWL_BUTTON_SELECTOR       = "#sliderContainer > div > div"
IMAGE_CRAWL_UNIQUE_IDENTIFIERS    = ["#NEW_CAPTCHA", "#captchaMask"]

PUZZLE_BUTTON_SELECTOR       = 'aside[aria-modal=true] div[style="width: 40px; height: 40px; transform: translateX(0px);"]'
PUZZLE_PUZZLE_IMAGE_SELECTOR = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=false]"
PUZZLE_PIECE_IMAGE_SELECTOR  = "aside[aria-modal=true] div[aria-hidden=true] > div > div > img[draggable=true]"
PUZZLE_UNIQUE_IDENTIFIERS    = ["aside[aria-modal=true]"]

CAPTCHA_PRESENCE_INDICATORS  = [PUZZLE_BUTTON_SELECTOR, "#NEW_CAPTCHA", "#captchaMask"]
```
Versi SDK (alternatif): puzzle=".DfwepB", pieceContainer="#puzzleContainer", piece="#puzzleImgComponent", button="#sliderContainer > div > div".

## Algoritma IMAGE_CRAWL (replika persis ext)

### Konstanta
```js
SCATTER_SWEEP = true;  SCATTER_BLOCK_PX = 30;
GESTURE_AMP_U = 1.5;   GESTURE_PASSES = 4;  GESTURE_PACE_MS = 2;
SWING_SAFE_PX = 12;
PAUSE_BEFORE_NUDGE_MS = [900, 2100];  PAUSE_BEFORE_RELEASE_MS = [750, 1450];
SKIP_CAP = 3;  PRESS_SETTLE_MS = 150;  SAMPLE_SETTLE_MS = 20;
OVERSHOOT_PX = 15;  MIN_TRAJECTORY_ROWS = 12;
```

### Flow
```
1. refresh image crawl (klik reset, tunggu gambar ganti)
2. puzzle_b64 = elementToDataUrl(IMAGE_CRAWL_PUZZLE_IMAGE)
3. info = POST /shopee-image-crawl-pre-analyze {image_b64: puzzle}
   → {slideXProportion, skipRecommended}
   - kalau skipRecommended && attempt < SKIP_CAP → refresh, ulang (attempt+1)
   - kalau slideXProportion >= 0.99 && attempt < SKIP_CAP → refresh, ulang
4. piece_b64 = elementToDataUrl(IMAGE_CRAWL_PIECE_IMAGE)
5. sweep trajectory (down di button center, jangan lepas):
   limit = puzzleWidth * 0.85 ; mouseStep = 3
   blok 30px, tiap blok pixel 0,3,6..<30 (di-scatter acak urutannya)
   tiap pixel: mouse.move(btnCx+pixel, btnCy-pixel)  # diagonal!
     SAMPLE_SETTLE_MS (20ms)
     ele = {pixels_from_slider_origin: pixel,
            piece_rotation_angle: rotateAngleFromStyle(piece.style),
            piece_center: {proportionX: round((pieceCenterX-containerX)/containerW,4),
                           proportionY: round((pieceCenterY-containerY)/containerH,4)}}
     push; kalau piece berhenti ≥ 10/3 ≈ 4x → stop
     kalau piece_center.proportionX >= slideXProportion sejak stopPx, & maju ≥ OVERSHOOT_PX → stop
   sort ascending pixels_from_slider_origin ; minimal MIN_TRAJECTORY_ROWS(12)
6. solution = POST /shopee-image-crawl {puzzle_image_b64, piece_image_b64, slide_piece_trajectory} 
   → pixelsFromSliderOrigin  ← JARAK DRAG FINAL (px)
7. GESTURE SWING (umat manusia):
   maxPx = puzzleWidth * 0.85 ; toU(px)=px/maxPx*4-2 ; toPx(u)=(u+2)/4*maxPx
   aimU = toU(solution)
   passes=4: a = 1.5*(1-c/4); clamp ke room; sisi selang-seling (+a, -a)
   leg(from,to,step): move bertahap + jitter y ±0.8, pace 2ms
   leg(...,13) tiap pass; leg(at, solution, 15) terakhir
   releasePx = toPx(round((toU(solution)+0.02)*1e4)/1e4)
   pause 900-2100ms → move ke releasePx → pause 750-1450ms → mouseUp
```

### PUZZLE (slide)
```
button_bbox=box(PUZZLE_BUTTON); sx,sy=center
mouse.move; down; drag 10px log(1+px)  # buka papan
puzzle=elementToDataUrl(PUZZLE_PUZZLE_IMAGE); piece=...PIECE_IMAGE
prop = POST /puzzle {puzzleImageB64,pieceImageB64} → slideXProportion
bar_w = width(PUZZLE_PUZZLE_IMAGE)   # = lebar IMAGE, BUKAN track-grip
dist = int(prop * bar_w)
drag sx+px, sy+log(1+px) ; mouse.up
```

### IMAGE_DRAG (drag piece + Verify)
```
piece=<img>; puzzle=<canvas>
{proportionalPoints:[{proportionX,proportionY}]} = POST /shopee-image-drag {puzzleImageB64,pieceImageB64}
bbox=viewportRect(puzzle); answerX=bbox.x+prop[0].proportionX*bbox.width; answerY=...
mouseApproach(start); mouse.down; bezier 20 titik ke (answerX,answerY); mouse.up(answerX,answerY)
clickElement(IMAGE_DRAG_VERIFY)  # KLIK VERIFY!
```

## TRUSTED INPUT
Ext pakai `chrome.debugger` → CDP `Input.dispatchMouseEvent` (`dispatchTrustedMouse`: `mousePressed/mouseReleased/mouseMoved`, `button/buttons/pointerType`). Playwright `page.mouse.*` = CDP trusted yang setara. JANGAN dispatch `MouseEvent`/`PointerEvent` sintetik via JS (kecuali fallback).

## Deploy modern (3 cara, dari launcher.py)
1. **`make_playwright_solver_context(pw, api_key, ...)`** — `launch_persistent_context` + `--load-extension=<ext_unpacked>` (paling gampang).
2. **`make_nodriver_solver(api_key, **kw)`** — nodriver + `--load-extension` (paling stealth).
3. **`make_undetected_chromedriver_solver(api_key, ...)`** — undetected_chromedriver + ext.
Ext di-download dari GitHub zip → unpack → temp dir → inject api key ke file ext → `--load-extension=<dir>` + `--disable-features=DisableLoadExtensionCommandLineSwitch`.

## Catatan kredit
- ~$0.0020/solve, 25 kredit gratis.
- **Hemat:** hash gambar puzzle → cache jawaban per-hash (puzzle sama = skip API).
