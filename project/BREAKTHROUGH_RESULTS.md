# 🎉 BREAKTHROUGH — Captcha Shopee TEMBUS (2026-10-15)

## Hasil run terakhir nomor `+62 877 6491 2714`

```
PHONE=87764912714 CHANNEL=wa PROXY=gb.vsproxy.org:10000
SUBMIT: trusted:button:has-text('BERIKUTNYA')@952,356
TOS setuju clicked {'x': 707.5, 'y': 516}
→ CAPTCHA LOLOS
→ OTP WhatsApp terkirim: "Kode OTP telah dikirim via WhatsApp ke (+62) 877 6491 2714"
```

**Screenshot bukti:** `shots/v6_87764912714_otp_modal.png`
Modal "Masukkan Kode OTP" + 6 field + countdown resend + tombol LANJUT.

## Kunci sukses (3 fix)

| # | Fix | Efek |
|---|---|---|
| 1 | **Deteksi tipe dari SELECTOR** (bukan teks) — IC_PIECE → image_crawl | endpoint benar |
| 2 | **Kredit SadCaptcha baru** `6bab1591...` (25 kredit) | API bisa dipanggil |
| 3 | **v6 patched** (fallback grip, 401 handling, dry-run) | pipeline solid |

## Kredit terpakai
- Sebelum: 25
- Sesudah: 23 → **2 solve** (pre-analyze + image-crawl)

## Fix tambahan (post-run)
`JS_STATE` di-update: sekarang deteksi `"Masukkan Kode OTP"` → `OTP`, dan `"Buat password"` → `PASSWORD`. Sebelumnya run ini dapat `STATE: ?` walau captcha lolos (cosmetic).

## Kredensial aktif

| Item | Nilai |
|---|---|
| SadCaptcha key | `6bab1591e2a29076ce13f7c9681fc62e` (23 kredit) |
| Bot autoreg | `8980993310:AA...` → **@tokn_aiBot** |
| Bot lama (idle) | `8046106656:AA...` → @Owerte_bot |
| Proxy ID | `gb.vsproxy.org:10000` (vsproxy, sessttl.5) |

## File terkait
- `shopee_v6.py` — solver (patched: selector-first detect + JS_STATE baru + dry-run)
- `shopeebot.py` — Telegram bot wrapper
- `bot_key.txt` — key SadCaptcha runtime
- `/tmp/shopee_bot_token_v2` — token @tokn_aiBot

## Next
- OTP 6-digit masuk via WA → tinggal input → step 2 "Buat password" → selesai akun
- Pipeline auto-deteksi `PASSWORD` state sekarang (buat lanjut step berikutnya)
