"""Driver chain signup Shopee (desktop) — JS-only, robust SPA.

Masalah: halaman Shopee punya overlay (vwqiT4) + React hydration → locator
Playwright (.click) hang "intercepts pointer events". Solusi: semua interaksi
via page.evaluate() + element.click() langsung, tanpa nunggu stable/visible.

Form desktop (dari screenshot f_before.png):
  input[0] = "No. HP atau alamat email"
  input[1] = "Kata Sandi"
  button   = "Daftar Log in" (merah) | kadang "BERIKUTNYA"

Alur: goto → dismiss lang → isi phone → isi password → cek TOS → klik submit
      → tunggu /anti_fraud/captcha/generate → solve via tools/ui_solver
"""
import time
from pathlib import Path

SIGNUP = "https://shopee.co.id/buyer/signup"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
SHOT = Path("/root/shopee-farm/shots")
SHOT.mkdir(parents=True, exist_ok=True)


def new_context(browser, proxy=None):
    kw = dict(user_agent=UA, locale="id-ID", viewport={"width": 412, "height": 915},
              is_mobile=True, has_touch=True)
    if proxy:
        kw["proxy"] = {"server": proxy}
    return browser.new_context(**kw)


# ---------------- JS helpers (in-page) ----------------

JS_DISMISS_LANG = r"""
() => {
  // modal "Pilih bahasa Anda" — cari tombol persis
  const els = [...document.querySelectorAll('button,div,span,a,li')];
  const byText = (re) => els.find(e => re.test((e.textContent||'').trim()) && e.offsetParent !== null);
  let hit = byText(/^bahasa indonesia$/i) || byText(/^indonesia$/i) || byText(/^bahasa\b/i);
  if (hit) { hit.click(); return 'id'; }
  return null;
}
"""

JS_FILL = r"""
(args) => {
  const [idx, val] = args;
  const inputs = [...document.querySelectorAll('input')]
      .filter(i => i.type==='tel' || i.type==='password' || i.type==='text' || i.type==='email'
                   || i.offsetParent !== null);
  if (!inputs[idx]) return {ok:false, n:inputs.length};
  const el = inputs[idx];
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(el, '');
  el.dispatchEvent(new Event('input', {bubbles:true}));
  setter.call(el, val);
  el.dispatchEvent(new Event('input', {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
  return {ok:true, val:el.value, type:el.type};
}
"""

JS_CHECK_TOS = r"""
() => {
  const cb = [...document.querySelectorAll("input[type='checkbox']")].find(c=>!c.checked);
  if (cb) { cb.click(); return {checked: cb.checked}; }
  return {checked: null};
}
"""

JS_CLICK_SUBMIT = r"""
() => {
  const vis = (e) => { const r = e.getBoundingClientRect();
    return r.width > 2 && r.height > 2 && r.top < 2000 && r.left > -200; };
  const cands = [...document.querySelectorAll('button,a,div[role=button],span,div')];
  const pats = [/^kirim$/i, /kirim kode/i, /^berikutnya$/i, /^daftar$/i, /^daftar log in$/i];
  const txt = (e) => (e.childElementCount === 0 ? (e.textContent || '') : (e.textContent || '')).trim();
  for (const pat of pats) {
    // cari elemen dgn teks persis + visible (rect-based, bukan offsetParent)
    const hits = cands.filter(x => pat.test(txt(x)) && vis(x));
    // pilih yang paling spesifik (teks terpendek = leaf node)
    hits.sort((a, b) => txt(a).length - txt(b).length);
    for (const b of hits) {
      try {
        const r = b.getBoundingClientRect();
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        b.scrollIntoView({ block: 'center' });
        // pointer + mouse event sequence
        for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
          b.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, clientX: cx, clientY: cy,
            view: window, pointerId: 1, pointerType: 'mouse' }));
        }
        b.click();
        return txt(b).slice(0, 30) + '|' + Math.round(cx) + ',' + Math.round(cy);
      } catch (e) { /* try next */ }
    }
  }
  return null;
}
"""

# modal "Syarat & Ketentuan Akun Shopee" -> tombol "Setuju"
JS_CLICK_AGREE = r"""
() => {
  const cands = [...document.querySelectorAll('button,a,div[role=button],span')];
  const b = cands.find(x => /^setuju$/i.test((x.textContent||'').trim()) && x.offsetParent !== null);
  if (b) { b.click(); return true; }
  return false;
}
"""

JS_DOM_CAPTCHA = r"""
() => {
  const c = document.querySelector('#anti_fraud_captcha');
  const any = document.querySelector("[id*=captcha],[class*=captcha],[class*=verify]");
  return {container: !!c, any: !!any,
          visible: c ? (c.offsetParent !== null) : (any ? any.offsetParent!==null : false),
          text: any ? (any.textContent||'').trim().slice(0,120) : ''};
}
"""


def dismiss_lang(page):
    try:
        return page.evaluate(JS_DISMISS_LANG)
    except Exception:
        return None


def fill_field(page, idx, value):
    try:
        return page.evaluate(JS_FILL, [idx, value])
    except Exception as e:
        return {"ok": False, "err": str(e)[:80]}


def check_tos(page):
    try:
        return page.evaluate(JS_CHECK_TOS)
    except Exception:
        return {"checked": None}


def click_submit(page):
    try:
        return page.evaluate(JS_CLICK_SUBMIT)
    except Exception:
        return None


def dom_captcha(page):
    try:
        return page.evaluate(JS_DOM_CAPTCHA)
    except Exception:
        return {}


def open_and_submit(page, phone, password, slow=0.8, shot=None):
    steps = []
    page.goto(SIGNUP, wait_until="domcontentloaded", timeout=45000)
    time.sleep(3 * slow)

    l = dismiss_lang(page)
    steps.append(f"lang:{l}")
    time.sleep(1.5 * slow)

    ph = phone.lstrip("0") if phone.startswith("0") else phone
    r0 = fill_field(page, 0, ph)
    time.sleep(0.5 * slow)
    r1 = fill_field(page, 1, password)
    steps.append(f"fill0:{r0.get('ok')} fill1:{r1.get('ok')}")
    if shot:
        page.screenshot(path=str(SHOT / f"{shot}_filled.png"))

    t = check_tos(page)
    steps.append(f"tos:{t.get('checked')}")
    time.sleep(0.3)

    # tombol utk memicu OTP: "Kirim Kode" (form 2-langkah) ATAU "Berikutnya"/"Daftar"
    c = click_submit(page)
    steps.append(f"submit:{c}")
    time.sleep(2 * slow)

    # modal Syarat & Ketentuan -> klik Setuju
    agreed = False
    for _ in range(6):
        try:
            if page.evaluate(JS_CLICK_AGREE):
                agreed = True
                break
        except Exception:
            pass
        time.sleep(1)
    steps.append(f"agree:{agreed}")
    time.sleep(3 * slow)
    if shot:
        page.screenshot(path=str(SHOT / f"{shot}_submitted.png"))
    return {"steps": steps, "fill": [r0, r1], "tos": t, "submit": c, "agreed": agreed}


def wait_for_captcha(page, timeout=25):
    for _ in range(timeout):
        try:
            g = page.evaluate("() => (window.__shcap && window.__shcap.generate || []).length")
            if g:
                return "api"
            d = dom_captcha(page)
            if d.get("container") or d.get("any"):
                return "dom"
        except Exception:
            pass
        time.sleep(1)
    return None
