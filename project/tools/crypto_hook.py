"""Hook crypto — gegat AES key (16/32 byte) + payload plaintext.

Strategi:
  - wrap crypto.getRandomValues: rekam semua output (kandidat key/IV/nonce)
  - wrap TextEncoder.encode: rekam string yang di-encode (kandidat plaintext)
  - wrap btoa: rekam base64 input (mungkin plaintext sebelum encrypt)
  - retry loop supaya dapat run yg captcha-nya render
"""
import json
from pathlib import Path

HOOK_CRYPTO = r"""
(() => {
  if (window.__chk) return; window.__chk = true;
  window.__keys = [];      // getRandomValues outputs
  window.__enc = [];       // TextEncoder.encode inputs
  window.__b64 = [];       // btoa inputs

  const trim = (u8, n) => Array.from(u8.slice(0, n));

  const g = crypto.getRandomValues.bind(crypto);
  crypto.getRandomValues = function(arr) {
    const r = g(arr);
    try {
      const u = (arr instanceof Uint8Array) ? arr : new Uint8Array(arr.buffer||arr);
      window.__keys.push({len: u.length, hex: Array.from(u).map(b=>b.toString(16).padStart(2,'0')).join(''), t:Date.now()});
      if (window.__keys.length > 400) window.__keys.splice(0, 200);
    } catch(e){}
    return r;
  };

  try {
    const te = TextEncoder.prototype.encode;
    TextEncoder.prototype.encode = function(s) {
      try {
        if (typeof s === 'string' && s.length > 4) {
          window.__enc.push({s: s.slice(0, 600), len: s.length, t: Date.now()});
          if (window.__enc.length > 200) window.__enc.splice(0, 100);
        }
      } catch(e){}
      return te.apply(this, arguments);
    };
  } catch(e){}

  try {
    const b = window.btoa;
    window.btoa = function(s) {
      try { if (typeof s === 'string' && s.length > 8) {
        window.__b64.push({s: s.slice(0, 400), t: Date.now()});
        if (window.__b64.length > 200) window.__b64.splice(0, 100);
      } } catch(e){}
      return b.apply(this, arguments);
    };
  } catch(e){}

  return 'installed';
})();
"""


def install_crypto_hook(page):
    page.add_init_script(HOOK_CRYPTO)
    try:
        return page.evaluate(HOOK_CRYPTO)
    except Exception as e:
        return f"err: {e}"


def read_crypto(page):
    try:
        return page.evaluate("() => ({keys: window.__keys||[], enc: window.__enc||[], b64: window.__b64||[]})")
    except Exception as e:
        return {"error": str(e)}
