#!/usr/bin/env python3
"""pure_signup.py — #12: signup_by_otp via PAGE CONTEXT (fetch in-browser).

Kenapa page-context: sz-sdk (x-sap-ri/x-sap-sec/af-ac-enc-sz-token) di-generate
oleh JS+WASM di halaman. fetch() dari dalam page OTOMATIS ter-sign SDK.
Jadi ini "pure API call" tapi signature valid — tanpa reverse sz-sdk.

Dipakai sebagai FALLBACK setelah OTP: kalau klik DAFTAR (UI) gagal, coba ini.
Signature diambil dari page (page.evaluate fetch).

Catatan: tetap butuh browser hidup (SDK di page). Tapi step-nya API (fetch JSON),
bukan klik UI — lebih robust & scriptable.

Usage (library): from pure_signup import signup_by_otp_page
"""
import hashlib


def _hash_pw(password: str) -> str:
    md5h = hashlib.md5(password.encode()).hexdigest()
    return hashlib.sha256(md5h.encode()).hexdigest()


def signup_by_otp_page(page, password: str, otp_token: str = "", security_fp: str = "") -> dict:
    """Panggil signup_by_otp dari dalam page (fetch ter-sign SDK)."""
    hashed = _hash_pw(password)
    js = """async (args)=>{
      try{
        const cks=document.cookie.split('; ').reduce((a,c)=>{const i=c.indexOf('=');a[c.slice(0,i)]=c.slice(i+1);return a;},{});
        const body={
          otp_token: args.otp_token||'',
          password: args.hashed,
          stay_logged_in: true,
          client_identifier: {security_device_fingerprint: args.fp || cks['_sapid'] || ''}
        };
        const r=await fetch('/api/v4/account/signup_by_otp',{
          method:'POST', credentials:'include',
          headers:{'Content-Type':'application/json','x-api-source':'pc',
                   'x-requested-with':'XMLHttpRequest'},
          body: JSON.stringify(body)
        });
        let j=null; try{j=await r.json();}catch(e){j={parse_err:String(e)};}
        return {status:r.status, json:j};
      }catch(e){return {status:-1, err:String(e)};}
    }"""
    try:
        return page.evaluate(js, {"hashed": hashed, "otp_token": otp_token, "fp": security_fp})
    except Exception as e:
        return {"status": -2, "err": str(e)[:120]}


def probe_anti_fraud_headers(page) -> dict:
    """Cek header anti-fraud yang SDK sisipkan (bukti SDK aktif)."""
    js = """async ()=>{
      try{
        const r=await fetch('/api/v4/account/basic/get_account_info',
          {headers:{'x-api-source':'pc','x-requested-with':'XMLHttpRequest'},credentials:'include'});
        return {status:r.status};
      }catch(e){return {err:String(e)};}
    }"""
    try:
        return page.evaluate(js)
    except Exception as e:
        return {"err": str(e)[:100]}


if __name__ == "__main__":
    print("pure_signup: module. import & pakai signup_by_otp_page(page, pw, otp_token, fp)")
    print("hash('PASS_REDACTED') =", _hash_pw("PASS_REDACTED"))
