"""Gegat kunci AES dari SDK captcha Shopee (internal webpack bundle).

Masalah: CryptoJS TIDAK di window — di-bundle internal (webpack). 
Solusi: hook webpack module cache. Saat SDK call CryptoJS.AES.encrypt/decrypt,
kita gegat (key, iv) yang dipakai.

Dua pendekatan (dipasang sekaligus):
  1. Patch __webpack_require__ / module.exports: bungkus fungsi yang
     punya bentuk AES.encrypt/decrypt (cari objek dengan .encrypt+.decrypt+keySize).
  2. Patch WebCrypto (crypto.subtle.decrypt) + btoa/atob jadi fallback.

Hasil gegat → window.__aes_hits, window.__maybe_keys.
"""
import json
from pathlib import Path

CAP_DIR = Path("/root/shopee-farm/captcha_re")
CAP_DIR.mkdir(parents=True, exist_ok=True)
KEY_FILE = CAP_DIR / "aes_keys.json"
KEY_JS = CAP_DIR / "grab_aes_keys.js"

GRAB_JS = r"""
(() => {
  if (window.__aesgrab) return "already";
  window.__aesgrab = true;
  window.__aes_hits = [];
  window.__maybe_keys = [];

  const looksLikeKey = (k) =>
    k && (typeof k === 'string' || k.length !== undefined) &&
    ((typeof k === 'string' && k.length >= 8 && k.length <= 64) || k.words);

  const rec = (op, key, iv, dataLen) => {
    try {
      window.__aes_hits.push({
        op, ts: Date.now(),
        key: (typeof key === 'string') ? key : (key && key.toString ? key.toString() : String(key)),
        iv: (typeof iv === 'string') ? iv : (iv && iv.toString ? iv.toString() : (iv ? String(iv) : null)),
        dataLen: dataLen || null
      });
    } catch(e){}
  };

  // --- Approach 1: patch CryptoJS jika ada di window ---
  const patchCW = (C) => {
    if (!C || !C.AES || C.AES.__p) return false;
    const oe = C.AES.encrypt, od = C.AES.decrypt;
    C.AES.encrypt = function(data, key, cfg) {
      rec('enc', key, cfg && cfg.iv, data && data.sigBytes);
      return oe.apply(this, arguments);
    };
    C.AES.decrypt = function(data, key, cfg) {
      rec('dec', key, cfg && cfg.iv, data && data.sigBytes);
      return od.apply(this, arguments);
    };
    C.AES.__p = true;
    return true;
  };
  if (patchCW(window.CryptoJS)) window.__maybe_keys.push('window.CryptoJS patched');

  // --- Approach 2: supervisi webpack chunk registry ---
  // Setiap webpack bundle mendaftarkan window.webpackChunk* = array pusher.
  const hookChunk = (name) => {
    const arr = window[name];
    if (!Array.isArray(arr) || arr.__hooked) return;
    const origPush = arr.push.bind(arr);
    arr.push = function(chunk) {
      try {
        const mods = chunk && chunk[1]; // {id: factory}
        if (mods && typeof mods === 'object') {
          for (const id in mods) {
            const f = mods[id];
            if (typeof f === 'function' && !f.__wrapped) {
              mods[id] = function() {
                try { patchCW(this && this.CryptoJS); } catch(e){}
                const m = f.apply(this, arguments);
                // scan module exports untuk AES-like object
                try {
                  if (m && typeof m === 'object') {
                    if (m.AES && m.AES.encrypt) patchCW(m);
                    for (const kk in m) {
                      const v = m[kk];
                      if (v && typeof v === 'object' && v.AES && v.AES.encrypt) patchCW(v);
                    }
                  }
                } catch(e){}
                return m;
              };
              mods[id].__wrapped = true;
            }
          }
        }
      } catch(e){}
      return origPush.apply(this, arguments);
    };
    arr.__hooked = true;
    window.__maybe_keys.push('chunk hooked: ' + name);
  };

  for (const k of Object.keys(window)) {
    if (/^webpackChunk/.test(k)) hookChunk(k);
  }
  // webpack juga kadang muncul belakangan
  let tries = 0;
  const iv = setInterval(() => {
    for (const k of Object.keys(window)) if (/^webpackChunk/.test(k)) hookChunk(k);
    if (++tries > 40) clearInterval(iv);
  }, 250);

  // --- Approach 3: WebCrypto subtle fallback ---
  try {
    if (window.crypto && crypto.subtle && !crypto.subtle.__p) {
      const od = crypto.subtle.decrypt.bind(crypto.subtle);
      const oe = crypto.subtle.encrypt.bind(crypto.subtle);
      crypto.subtle.decrypt = function(alg, key, data) {
        try { window.__aes_hits.push({op:'subtle_dec', ts:Date.now(), alg:JSON.stringify(alg)}); } catch(e){}
        return od(alg, key, data);
      };
      crypto.subtle.encrypt = function(alg, key, data) {
        try { window.__aes_hits.push({op:'subtle_enc', ts:Date.now(), alg:JSON.stringify(alg)}); } catch(e){}
        return oe(alg, key, data);
      };
      crypto.subtle.__p = true;
    }
  } catch(e){}

  return "installed";
})();
"""


def grab_keys(page):
    KEY_JS.write_text(GRAB_JS)
    page.add_init_script(GRAB_JS)
    r = page.evaluate(GRAB_JS)
    return r


def read_keys(page):
    return page.evaluate("() => ({hits: window.__aes_hits||[], notes: window.__maybe_keys||[]})")


def dump_keys(page=None, path=KEY_FILE):
    if page is None:
        return None
    data = read_keys(page)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return data
