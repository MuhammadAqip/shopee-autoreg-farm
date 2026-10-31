/*
 * frida_shopee_signup.js — Hook Shopee Android (id.co.shopee) registration flow
 *
 * Tujuan:
 *   1. Lihat bagaimana app generate `security_device_fingerprint` + `af-ac-enc-dat`
 *   2. Log payload get_settings_v2 / send_otp asli (dari app, bukan web)
 *   3. Cari & hook fungsi yang cek captcha → force-return "verified"
 *
 * Pakai (HP rooted / frida-server jalan):
 *   frida -U -f id.co.shopee -l frida_shopee_signup.js --no-pause
 * atau lewat gadget (non-root):
 *   patched APK + frida-gadget
 */

'use strict';

const PKG = 'id.co.shopee';

function ts() { return new Date().toISOString().substr(11, 8); }
function log(tag, msg) { console.log(`[${ts()}][${tag}] ${msg}`); }

// ── 1. Temukan class native crypto/fingerprint Shopee ──────────────────────
Java.perform(function () {
  log('init', 'Java.perform OK — target: ' + PKG);

  // 1a. Cari class yang namanya nyimpen "fingerprint" / "encrypt" / "sign"
  const KEYWORDS = ['afacenc', 'Fingerprint', 'SecurityDevice', 'Encrypt',
                    'Captcha', 'Otp', 'DeviceId', 'Security'];
  Java.enumerateLoadedClasses({
    onMatch: function (name) {
      for (const k of KEYWORDS) {
        if (name.indexOf(k) !== -1) {
          log('class', name);
          break;
        }
      }
    },
    onComplete: function () { log('enum', 'selesai'); }
  });

  // 1b. Hook OkHttp — lihat SEMUA request signup/otp + header asli
  try {
    const Buffer = Java.use('okio.Buffer');
    const Interceptor = Java.use('okhttp3.Interceptor');
    // hook lewat RealCall supaya dapat URL + headers + body
    const RealCall = Java.use('okhttp3.internal.connection.RealCall$AsyncCall');
    RealCall.execute.implementation = function () {
      const req = this.getRequest();
      const url = req.url().toString();
      if (/api\/v4|otp|signup|register|login/.test(url)) {
        log('HTTP', req.method() + ' ' + url);
        try {
          const headers = req.headers();
          for (let i = 0; i < headers.size(); i++) {
            const n = headers.name(i).toLowerCase();
            if (n.indexOf('csrf') !== -1 || n.indexOf('af-ac') !== -1 ||
                n.indexOf('x-api') !== -1 || n.indexOf('fingerprint') !== -1) {
              log('  hdr', headers.name(i) + ': ' + headers.value(i));
            }
          }
          const body = req.body();
          if (body) {
            const buf = Buffer.$new();
            body.writeTo(buf);
            log('  body', buf.readUtf8().substring(0, 400));
          }
        } catch (e) { log('  err', e); }
      }
      return this.execute();
    };
    log('hook', 'OkHttp RealCall hooked');
  } catch (e) {
    log('hook', 'OkHttp fail: ' + e);
  }

  // 1c. Hook SSL write — capture plaintext sebelum enkripsi (fallback)
  try {
    const SSLSocket = Java.use('com.android.org.conscrypt.ConscryptEngineSocket');
    log('note', 'ConscryptSocket tersedia (fallback packet-level via tcpdump)');
  } catch (e) {}

  // 1d. Cari class captcha — hook fungsi yang return "solved/verified"
  const CAPTCHA_HINTS = ['captcha', 'Captcha', 'verify', 'Verify', 'Security'];
  Java.enumerateLoadedClasses({
    onMatch: function (name) {
      if (!/shopee/i.test(name)) return;
      for (const h of CAPTCHA_HINTS) {
        if (name.indexOf(h) !== -1) {
          log('captcha-class', name);
          try {
            const C = Java.use(name);
            for (const m of C.class.getDeclaredMethods()) {
              const mn = m.getName();
              if (/captcha|verified|isValid|check|success/i.test(mn)) {
                log('  method', mn + ' ' + m.getReturnType().getName());
              }
            }
          } catch (e) {}
          break;
        }
      }
    }, onComplete: function () {}
  });

  // 1e. Bypass root/emulator detect (umum di app register flow)
  try {
    const RootDetect = Java.use('java.io.File');
    RootDetect.exists.implementation = function () {
      const p = this.getAbsolutePath();
      if (/su$|magisk|superuser|busybox|xposed/i.test(p)) {
        log('root-bypass', p + ' -> false');
        return false;
      }
      return this.exists();
    };
    log('bypass', 'root-detect File.exists patched');
  } catch (e) {}

  log('ready', 'hook terpasang. buka menu Daftar di app Shopee.');
});

// ── 2. Hook native layer (JNI) ─────────────────────────────────────────────
try {
  const symbols = ['AES_encrypt', 'base64_encode', 'SHA256', 'HmacSHA256'];
  for (const s of symbols) {
    const addr = Module.findExportByName(null, s);
    if (addr) {
      Interceptor.attach(addr, {
        onEnter: function (args) { this.s = s; },
        onLeave: function (ret) { /* log('native', this.s); */ }
      });
    }
  }
  log('native', 'native symbol scan selesai');
} catch (e) {
  log('native', 'fail: ' + e);
}

/* ──────────────────────────────────────────────────────────────────────────
   CATATAN PEMAKAIAN
   ──────────────────────────────────────────────────────────────────────────
   1. HP rooted + frida-server:
        adb push frida-server /data/local/tmp/ && adb shell su -c /data/local/tmp/frida-server &
        frida -U -f id.co.shopee -l frida_shopee_signup.js --no-pause
   2. HP non-root (gadget):
        frida-gadget inject ke APK, repack, install
   3. Output penting:
        - header `x-csrftoken`, `af-ac-enc-dat`, `security_device_fingerprint` apa adanya
        - payload JSON get_settings_v2 / send_otp dari app
        - nama class captcha + method verified
   4. Kalau app pakai certificate pinning → aktifkan frida SSL unpinning (lihat script
      universal-unpinning.js) supaya OkHttp hook kebaca.
   ────────────────────────────────────────────────────────────────────────── */
