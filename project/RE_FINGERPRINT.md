# Reverse Engineering Shopee APK — Cara `security_device_fingerprint` Bekerja

**Target:** `com.shopee.id` v3.83.36 (versionCode 38336) · XAPK 114.9 MB
**Metode:** Static RE (unzip → `strings` → `nm` → jadx) · **tanpa emulator**
**Tanggal:** 2026-10-14

---

## 📦 Struktur APK (XAPK bundle)

```
shopee.apk (XAPK)
├── com.shopee.id.apk        76.5 MB  (base — 16 DEX)
├── config.arm64_v8a.apk     37.3 MB  (native libs, 166 × .so)
├── config.mdpi.apk           1.0 MB  (resources)
└── manifest.json
```

- targetSdk 36, minSdk 23
- **16 DEX** (~100 MB bytecode), 13.291 file Java setelah decompile
- **166 native libraries**

---

## 🎯 TEMUAN INTI — Chain Fingerprint

```java
// com/shopee/app/network/request/login/o.java
.security_device_fingerprint(
    SPSSDKDelegate.INSTANCE.getDeviceFingerPrint(ShopeeApplication.d())
)
```

```java
// com/shopee/app/util/tongdun/SPSSDKDelegate.java
private static com.shopee.app.util.tongdun.a deviceFingerPrintImpl = new a();

static final class a implements com.shopee.app.util.tongdun.a {
    public String a(Context context) {
        return SHPSSDK.getInstance().getRiskToken(context);   // ← INTI
    }
}
```

**Jadi:**

```
security_device_fingerprint
   = SHPSSDK.getInstance().getRiskToken(context)
   = Tongdun (同盾) risk engine
   = libshpssdk.so → libtongdun.so
```

---

## 🔍 Bukti Berlapis

### 1. Field payload (`ClientIdentifier.java`)
```java
public final class ClientIdentifier {
    @c("clientid")                    String clientId;
    @c("client_ip")                   String clientIp;
    @c("device_fingerprint")          okio.h deviceFingerprint;
    @c("deviceid")                    okio.h deviceId;
    @c("security_device_fingerprint") String securityDeviceFingerprint;
}
```

### 2. Native library `libshpssdk.so` (5.6 MB)
```
strings → libtongdun.so
          getEncryptSharedPreferencesString
          setEncryptSharedPreferencesString
          PARTNER_CODE
```
→ **Tongdun SDK tertanam** (同盾科技 — vendor anti-fraud China #1).

### 3. Package `com.shopee.shpssdk` (strings dari DEX)
```
Lcom/shopee/shpssdk/SHPSSDK;              ← main
Lcom/shopee/shpssdk/ShpssInstall;         ← install-time
Lcom/shopee/shpssdk/SPSAssessRisk;        ← ASSESS RISK
Lcom/shopee/shpssdk/SPSRiskTokenCallback; ← callback token
Lcom/shopee/shpssdk/SPSType;              ← tipe
Lcom/shopee/shpssdk/wvvvuvww;             ← obfuscated
```

### 4. Library pendukung
| Library | Fungsi |
|---|---|
| `libshpssdk.so` | Shopee Shield (wraps Tongdun) |
| `libshopeeaegis.so` | "Aegis" — crypto (AES-CBC, CCM) |
| `libHashSecurity.so` | JNI hash/keys (bke = ShopeePay) |
| `libtongdun.so` | Tongdun engine (referenced) |

### 5. `libshopeeaegis.so` — operator crypto
```
Aegis::getInstance() / instance          — singleton
Aegis::parse(string)                     — parser
Aegis::prism(int, in, len, out, outlen, string)  — transform utama
Aegis::missileFire(int, in, len, out, outlen)    — v1
Aegis::missileFire(int, in, len, in2, len2, out, outlen) — v2
Aegis::missileCount(int, int)
Aegis::tugWar(int, int, int)             — anti-tamper
Aegis::snowDon(int, string, len)         — enkripsi/dekripsi
aes_decrypt_cbc, ccm_*, modelx_autopilot_ccm, modelx_charge_ccm
```
Java class: `com.shopee.sz.reinforce.Aegis`

### 6. `libHashSecurity.so` JNI exports
```
Java_com_shopee_bke_biz_twoway_auth_security_HashSecurity_getAppNativeAuthHashKey
Java_com_shopee_bke_biz_twoway_auth_security_HashSecurity_getHashCode
Java_com_shopee_bke_biz_twoway_auth_security_HashSecurity_getMMKVEncryptKey
Java_com_shopee_bke_biz_twoway_auth_security_HashSecurity_getBksAesKeyLive
Java_com_shopee_bke_biz_twoway_auth_security_HashSecurity_getBodyEncryptionRsakey
...
```
→ package `com.shopee.bke.*` = **ShopeePay / banking security**.

---

## 🔄 Alur Lengkap (rekontruksi)

```
╔══════════════════════════════════════════════════════════════╗
║  APP START                                                   ║
║  SHPSSDK.init()  → libshpssdk.so + libtongdun.so dimuat      ║
║  (ShpssInstall — daftar perangkat saat install pertama)      ║
╚══════════════════════════════════════════════════════════════╝
                          │
                          ▼
  SPSSDKDelegate.getDeviceFingerPrint(context)
     │
     ├─ feature toggle (e46af15b..., 0d6302e7...) aktif?
     │
     ▼
  SHPSSDK.getInstance().getRiskToken(context)
     │  (async — SPSRiskTokenCallback)
     ├─ Tongdun engine kumpulkan sinyal perangkat
     ├─ hitung risk score
     ├─ enkripsi (AES-CBC / CCM via libshopeeaegis)
     └─ hasilkan "RiskToken" (dfp)
                          │
                          ▼
  deviceFingerprintImpl.a(context) → String token
                          │
                          ▼
  ClientIdentifier.securityDeviceFingerprint = token
                          │
                          ▼
  POST /api/v4/otp/get_settings_v2
       client_identifier.security_device_fingerprint = "<token>"
                          │
                          ▼
  Server Shopee validasi token → putuskan:
       need_captcha: true/false
       risk level
```

---

## 📋 Sinyal yang Kemungkinan Dipanen Tongdun

Dari permission manifest + pola SDK anti-fraud:

| Kategori | Contoh |
|---|---|
| Hardware | build fingerprint, model, serial, IMEI (bila diizinkan) |
| OS | versi Android, patch level, rooted?, emulator? |
| Network | IP, operator, WiFi SSID, proxy? |
| App | list aplikasi terinstall, installer package, Xposed/Magisk |
| Behavioral | sensor (akselerometer), touch timing |
| Storage | `getEncryptSharedPreferencesString` — data terenkripsi |
| Integrity | signature APK, tamper check (`tugWar`) |

`libshopeeaegis.so` menyediakan crypto untuk enkripsi token (`snowDon`, `aes_decrypt_cbc`).

---

## 💡 Zona Prioritas Telaah Lanjut

1. **`getRiskToken()` internals** — butuh **dynamic Frida** (hook `SHPSSDK.getRiskToken` → lihat input/output) atau **emulasi libtongdun** (ARM, butuh QEMU/KVM).
2. **`PARTNER_CODE`** — tongdun partner ID Shopee, kemungkinan di `AndroidManifest` atau `.so` strings (encrypted).
3. **`SPSAssessRisk`** — class penilai risiko; nama method-nya kunci logika scoring.
4. **`libHashSecurity.so`** — kunci AES/RSA aplikasi (bke domain).
5. **`tugWar()`** — anti-tamper, kalau lolos bisa jalankan flow tanpa trigger.

---

## ⚠️ Batasan (Jujur)

| Bisa (statik) | Tidak bisa (butuh runtime) |
|---|---|
| Struktur APK + 16 DEX | **Jalankan `getRiskToken()` live** |
| Nama class/method/library | **Emulasi `.so` ARM** (butuh KVM) |
| Algoritma crypto (`aes_decrypt_cbc`) | **Lihat input/output token asli** |
| Chain call (SPSSDKDelegate → SHPSSDK) | **Bypass `tugWar` anti-tamper** |
| Field payload API | **Eksekusi penuh di emulator** |

**Kenapa tidak bisa runtime:** VPS ini **tanpa KVM** + 2 core + 4 GB RAM → emulator Android mustahil. Dynamic analysis butuh:
- VPS dengan nested virtualization (KVM), **atau**
- HP Android + frida-server (jalankan `frida_shopee_signup.js` yang sudah disiapkan), **atau**
- Emulator ARM di mesin dengan akselerasi

---

## 🎁 Kesimpulan Praktis untuk Capture-Dari-Web

`security_device_fingerprint` **bukan hash statis** — ia **token terenkripsi** yang digenerate runtime oleh **engine Tongdun** berdasarkan puluhan sinyal perangkat. **Tidak bisa diformulasikan ulang** tanpa menjalankan SDK asli.

**Konsekuensi untuk farm:**
- Web flow (`shopee_client.py`) → butuh token valid dari sesi browser nyata (Playwright + JS bundle `browser-signals`) atau hook.
- App flow → butuh Frida hook untuk memanen token (`SPSSDKDelegate` hook).
- **Argumen terkuat untuk pakai emulator/HP** — hanya di sana SDK bisa jalan.

---

## 📦 Artefak

```
/root/apk_re/
├── extracted/                XAPK isi
├── base/                     16 DEX
├── nativelib/lib/arm64-v8a/  166 .so
├── decompiled/sources/       13.291 .java (jadx)
│   └── com/shopee/app/util/tongdun/SPSSDKDelegate.java   ← kunci
│   └── com/shopee/app/network/http/data/ClientIdentifier.java
│   └── com/shopee/app/network/request/login/o.java
├── shopee.apk                XAPK 114.9 MB
└── jadx/                     tool
```
