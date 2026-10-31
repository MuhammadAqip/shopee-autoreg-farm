# Shopee Auto-Register Farm (Playwright)

Auto-register Shopee Indonesia **berbasis browser nyata** — karena
`security_device_fingerprint` + `af-ac-enc-dat` di-generate oleh bundle
`browser-signals` di dalam halaman, dan captcha butuh konteks browser.
Requests polos **tidak bisa** (server menolak). Browser nyata menghasilkan
semua token otomatis.

---

## ⚡ Quick Start

```bash
cd /root/shopee-farm
source /root/sniffenv/bin/activate   # playwright + deps

# tes kering (tanpa jaringan)
python3 farm_browser.py --count 5 --dry-run

# registrasi nyata (butuh solver captcha + OTP sink)
export CAP_SOLVER=capsolver
export CAP_API_KEY=<key>
python3 farm_browser.py --count 10 --proxy-file proxies.txt

# satu akun, manual (lihat layar captcha)
python3 auto_reg.py --mode e2e --phone 081234567890
```

---

## 🧩 Komponen

```
shopee-farm/
├── farm_browser.py        ← RUNNER NYATA (multi-akun, browser)
├── auto_reg.py            ← satu akun, capture token (debug)
├── farm.py                ← runner lama (requests; mentok token, arsip)
├── core/
│   ├── accounts.py        ← generator identitas Indonesia
│   ├── device.py          ← spoof Android (IMEI Luhn, spc_id)
│   ├── shopee_client.py   ← client requests (endpoint terverifikasi)
│   └── store.py           ← SQLite resumable
├── tools/
│   ├── proxy.py           ← proxy pool + OTP sink (Manual/HTTP)
│   └── captcha.py         ← solver adapter (Capsolver/2Captcha)
├── panel/app.py           ← panel web zero-dep (port 8088)
├── mitm_addon.py          ← mitmproxy capture
├── frida_shopee_signup.js ← Frida hook app Android
├── SNIFF_A_RESULTS.md     ← endpoint + chain (BUKTI LIVE)
├── RE_FINGERPRINT.md      ← cara fingerprint bekerja (RE APK)
├── FRIDA_HOOK_RESULTS.md  ← hasil hook SHPSSDK
├── EMULATOR_E2E_RESULTS.md
└── EMULATOR_ARM64_RESULTS.md
```

---

## 🔗 Chain Registrasi (terverifikasi live)

```
GET /buyer/signup
  → gate bahasa ("Pilih Bahasa Anda" → Bahasa Indonesia)
  → isi input nomor (type=tel)
  → ceklis TOS → klik "Berikutnya"
  → modal "Simak Ketentuan Akun Shopee" → "Setuju"
  → POST /api/v4/otp/get_settings_v2      [200]
        {operation:8, phone:62xxx, supported_channels:[1,2,3,6,0,5],
         client_identifier:{security_device_fingerprint:"<token>"}}
     ← {need_captcha:true, captcha_scene:"signup", available_channels:[3,2,1]}
  → [CAPTCHA]  reCAPTCHA v2 (desktop) / slider geetest (mobile)
  → POST /api/v4/otp/send_otp  (dgn captcha token)     → SMS/WA
  → OTP dari sink → verify → akun
  → POST /api/v4/account/login_by_password             → session token
```

### Header yang WAJIB (terekam nyata dari browser)

```
x-api-source: pc            (desktop) | rweb (web mobile)
x-requested-with: XMLHttpRequest
x-csrftoken: <dari cookie csrftoken>
af-ac-enc-dat: b0c9718544dc2712     (16-hex, PER-REQUEST)
referer: https://shopee.co.id/buyer/signup
```

### Bentuk token (capture nyata)

```
security_device_fingerprint =
  gq2qri+snOezkf56H6Mk6g==|dZ2s8nLw...|3gfOxLDWFjGqHOl0|08|3
  └── base64 ──┘|└ base64 ┘|└── hex8 ──┘|op|ver
```
Format: `base64|base64|hex8|operation|version`. Di-generate runtime oleh
engine Tongdun (lihat RE_FINGERPRINT.md). **Browser menghasilkan ini otomatis** —
alasan runner berbasis browser, bukan requests.

---

## 🚧 Dua Slot Eksternal (yang disediakan pakai)

### 1. Captcha solver
```bash
export CAP_SOLVER=capsolver    # atau 2captcha / anticaptcha
export CAP_API_KEY=<key>
```
- Desktop signup → **reCAPTCHA v2** → `solve_recaptcha_v2(sitekey, url)`
- Mobile OTP  → **slider geetest** → `solve_geetest_slider(gt, challenge, url)`

### 2. OTP sink (nomor + pembaca SMS)
- `ManualOTP` — baca dari `otp.txt` (format `62812xxx:123456`)
- `HTTPOTP` — adapter provider SMS-activation generik

---

## 🔑 Kunci Anti-Deteksi (terpasang)

1. **Satu device = satu akun.** `spc_device_id` unik per akun.
2. **Proxy dipin per akun** — jangan ganti IP di tengah chain.
3. **Browser nyata** — token & captcha di-generate seperti user asli.
4. **Jeda antar akun** — registrasi cepat berturut = flag.

---

## 📊 Status (jujur, terbukti)

| Komponen | Status |
|----------|:-:|
| Chain UI sampai captcha | ✅ terbukti (screenshot) |
| Capture `security_device_fingerprint` asli | ✅ 139 char |
| Capture `af-ac-enc-dat` + `csrftoken` | ✅ |
| Endpoint `get_settings_v2` | ✅ 200 |
| Generator identitas + device spoof | ✅ (IMEI Luhn 200/200) |
| Store SQLite resumable + panel | ✅ |
| Multi-akun runner | ✅ (dry-run OK) |
| Solver captcha | slot siap (butuh API key) |
| OTP → verify → active | butuh OTP sink |
| Emulator (x86 + ARM) | ❌ native SHPSSDK crash / arch mismatch |

**Fondasi auto-regis SELESAI.** Yang tersisa = isi 2 slot eksternal
(solver + OTP), keduanya tinggal isi key/endpoint.

---

## ⚠️ Catatan

- **Proxy:** datacenter IP ditolak Shopee → pakai residential. Rotasi
  antar-akun, **jangan** di tengah chain.
- **Captcha:** reCAPTCHA v2 butuh sitekey dari DOM (`iframe[src*=recaptcha]`).
- **Verifikasi tetap server-side:** device spoof turunin deteksi duplikat,
  bukan menghapus OTP/risk-score.

## Export

- Panel → tombol `⬇ CSV` / `⬇ JSON` (port 8088)
