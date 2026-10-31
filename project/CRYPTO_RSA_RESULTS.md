# Shopee Captcha Crypto — RSA-1024 Reverse (BREAKTHROUGH)

**Sumber:** `bundle.a95de02.js` (799.992 bytes) — decompiled live dari `deo.shopeemobile.com`

## 🎯 Temuan inti

Payload captcha **BUKAN AES** — pakai **RSA-1024** (PKCS#1 v1.5):

```js
U = "<256 hex chars>"   // modulus
S = "010001"            // public exponent = 65537
function D(t){
  var n = new B;
  n.setPublic(U, S);
  e = n.encrypt(t);
  return typeof e === 'string' ? b64(e) : "";
}
```

### Parameter RSA
| Field | Nilai |
|---|---|
| Modulus (U) | 1024-bit (256 hex chars) — di `rsa_modulus.txt` |
| Public exponent (S) | `0x010001` = 65537 |
| Padding | PKCS#1 v1.5 (default jsencrypt) |
| Output | base64 |

### Artefak
- `rsa_modulus.txt` — modulus hex lengkap (256 chars)
- `bundle.js` — SDK asli (799KB, unminified-ish)

## Implikasi untuk pure-API

Endpoint yang **sebelumnya diasumsikan AES (`U2FsdGVkX1`) cuma sebagian**:
- `captcha/generate` — enkripsi payload request pakai **RSA** (fungsi D)
- `captcha/verify` — sama + signature

**Karena RSA = public-key**, enkripsi **bisa direplikasi tanpa secret server**. Kita cuma butuh:
1. Modulus + exponent (sudah di-ekstrak)
2. Plaintext body yang benar (dari capture)

→ Ini artinya **pure-API replikasi SANGAT mungkin**, tanpa perlu re-implement CryptoJS ataupun nembus IIFE.

## Implementasi Python

```python
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
import base64, re

mod_hex = open("rsa_modulus.txt").read().strip()
n = int(mod_hex, 16)
e = 65537
pub = rsa.RSAPublicNumbers(e, n).public_key()

def rsa_encrypt(plaintext: str) -> str:
    ct = pub.encrypt(plaintext.encode(), padding.PKCS1v15())
    return base64.b64encode(ct).decode()
```

Atau pakai `jsencrypt`-compatible lib:
```python
# pip install pycryptodome
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
key = RSA.construct((n, e))
cipher = PKCS1_v1_5.new(key)
ct = cipher.encrypt(plaintext.encode())
print(base64.b64encode(ct).decode())
```

## Chain pure-API lengkap

```
1. POST /api/v4/otp/get_settings_v2      (plaintext)  → need_captcha, captcha_app_key
2. POST /api/v4/anti_fraud/captcha/get_config (plaintext) → bundle_url, tracking_id
3. build payload → RSA_encrypt(json)     (CLIENT-SIDE, pake modulus publik)
4. POST /api/v4/anti_fraud/captcha/generate  {encrypted_data} → encrypted_data (puzzle img)
5. [SOLVE] → jawab puzzle (SadCaptcha API / vision)
6. RSA_encrypt(answer + trajectory) → POST /captcha/verify → captcha_token
7. POST /api/v4/otp/send_otp {captcha_token, ...} → WA/SMS
```

**Yang masih butuh browser:** cuma geometry puzzle (surface tertutup SDK). Sisanya 100% API-able.

## Kenapa ini baru terlihat

Capture sebelumnya (`sniff_A`) ga nangkep `captcha/generate` body plaintext karena dienkripsi. Sekarang modul RSA ketemu di bundle → bisa decrypt/reproduce.

## Next step
1. Decrypt `encrypted_data` contoh pakai private key? → **TIDAK BISA** (RSA publik tak bisa decrypt). Tapi kita tak perlu decrypt response — cuma reproduce request.
2. Ambil plaintext SEBELUM `D()` dipanggil → hook di browser: patch `D` untuk log input.
3. Test: RSA_encrypt({...}) → POST generate → bandingkan struktur response.
