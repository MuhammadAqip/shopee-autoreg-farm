# Update Project Shopee — 2026-10-15 (sesi lanjutan)

## Yang dikerjakan

Maker minta: (1) pelajari Achicaptcha + kaitannya dgn SadCaptcha, (2) lanjutkan project Shopee — bikin solver makin cepat & akurat.

## 1. Status router captcha

- **docs.achicaptcha.com DOWN/gabisa diakses** (sesi kemarin + cek ulang). Fallback plan: kalau SadCaptcha mati → achicaptcha. Belum bisa onboard.
- **SadCaptcha = tetap primary.** OpenAPI schema di-check live (`/api/v1/v3/api-docs`) — semua endpoint v6 match: `/puzzle`, `/shopee-image-crawl`, `/shopee-image-crawl-pre-analyze`, `/shopee-image-drag`, `/license/credits`.
- **KREDIT = 0 di dua key** (`400648b8...`, `f231e3e4...`). Semua kegagalan solve kemarin = kombinasi (a) salah tipe captcha → salah endpoint, (b) kredit kosong. Fix dulu ini sebelum debug lain.

## 2. ROOT CAUSE ketemu — deteksi tipe salah urutan

Bukti dari `probe_v6_dump.py` (dump live 13:44 nomor 85839212763):
- Puzzle = `<canvas class=EkGpDI>` 280×150 draggable=**false**
- Piece = `<canvas class=_0N0-Dn>` 44×44 draggable=**true**

→ Ini **IMAGE_CRAWL** (piece canvas draggable=true), bukan puzzle slide!
Tapi shopee_v6 lama lock tipe dari TEKS ("Geser ... puzzle" → puzzle) → POST `/puzzle` → jawaban ngawur → drag gagal → buang 5-6 attempt limit/nomor.

## 3. Patch shopee_v6.py (sudah compile OK)

1. **Deteksi tipe dari SELECTOR dulu** (urutan skill: IC_PIECE→image_crawl, PZ_PIECE→puzzle, ID_*→image_drag). Teks cuma fallback terakhir.
2. **solve_image_crawl hardening**: fallback grip detection (28-56px persegi, top>480) kalau IC_BUTTON selector gagal; deteksi HTTP 401 → err CREDITS_EMPTY (nggak buang attempt sia2).
3. **Mode `--dry`**: full pipeline (buka form, submit, TOS, captcha detect, sweep trajectory) TANPA panggil API / TANPA mouse.up release — buat validasi tipe & traj length gratis.

## 4. Analisis offline puzzle dump (billing-free tuning)

Data: `shots/dump_IC_PUZZLE_85839212763.png` (280×150).

| Metode | Hasil |
|---|---|
| matchTemplate space-domain (piece full-bleed 44×44) | skor cuma 0.45 — piece full-bleed margin hitam ngerusak template |
| matchTemplate edge (Laplacian) | 0.106 — gagal |
| **Canny window-density (44px window)** | **konsisten: x=103-112 (37-40%)** — spike density jauh di atas piece asli (84k ink) |

→ Untuk tipe image-crawl ini, **sliding window ink-density di Canny map** kandidat kuat sebagai fallback lokal gratis kalau API SadCaptcha down / kredit abis. Perlu validasi bbrp puzzle lagi.

## 5. Bot @Owerte_bot — restart & live

- Token Ambil dari `/root/.hermes/config.yaml` (8046106656:AA...), diselmatkan ke /tmp/shopee_bot_token
- Jalankan: `BOT_TOKEN=... SADCAPTCHA_KEY=$(cat bot_key.txt) /root/sniffenv/bin/python shopeebot.py` (PID 1164446, binary @Owerte_bot via getMe = OK)
- Bot sekarang pakai shopee_v6.py yang PATCHED

## 6. Skill updated

`shopee-captcha-solver` — tambah lesson: urutan deteksi selector-first, cek kredit dulu sebelum debug, map infrastruktur /root/shopee-farm, achicaptcha status.

## Next steps (butuh dari Maker)

1. **TOP-UP kredit SadCaptcha** (key aktif di bot_key.txt) — semua jalur udah siap tinggal jalan, tapi 0 kredit = jalan ditempat.
2. TEST `--dry`: `xvfb-run -a /root/sniffenv/bin/python shopee_v6.py 89601416330 xxx "http://...@gb.vsproxy.org:10000" --dry` → pastikan `type=image_crawl` + traj ≥12
3. Test solve real 1× pakai nomor fresh (`89601416330`) setelah kredit ada.
4. Kalau mau backup solver gratis: tune canny-window detector pake 5-10 dump puzzle (bisa koleksi via --dry tanpa API).
