"""Shopee anti_fraud captcha — hook browser (Playwright).

Strategi (reverse bundle.a95de02.js + capture network):
  SDK captcha generik (endpoint injected). Payload verify = KOORDINAT + TIMING:
    { captcha_id, captcha_source,
      captcha_top_left_x/y, captcha_box_width/height,        ← jawaban klik
      slider_start_pos/start_x/start_y/box_w/box_h/end_pos,  ← jawaban geser
      captcha_start_timestamp, captcha_end_timestamp, captcha_refresh_num }

  Endpoint (dari network capture):
    GET  /api/v4/anti_fraud/captcha/get_config
    POST /api/v4/anti_fraud/captcha/generate
    POST /api/v4/anti_fraud/captcha/verify        (atau feedback)
    POST /api/v4/anti_fraud/captcha/feedback/questions

Modul ini hook fetch/XHR DI DALAM halaman untuk:
  1. rekam payload generate (challenge + gambar)
  2. rekam request verify (format final jawaban)
  3. opsi auto-answer (placeholder — sambung solver sekali challenge diketahui)

Usage (dipanggil dari auto_reg/farm_browser):
    from captcha_hook import install_captcha_hook, dump_captcha_capture
    install_captcha_hook(page)
    ...
    dump_captcha_capture()
"""
import json
import os
from pathlib import Path

CAP_DIR = Path("/root/shopee-farm/captcha_re")
CAP_DIR.mkdir(parents=True, exist_ok=True)
CAP_FILE = CAP_DIR / "captcha_flow.jsonl"
BUNDLE_JS = CAP_DIR / "hook_inject.js"

# --- JS yang disuntik ke halaman: bungkus fetch + XHR ---
INJECT = r"""
(() => {
  if (window.__shcap_installed) return;
  window.__shcap_installed = true;
  window.__shcap = {generate: [], verify: [], config: [], feedback: [], all: []};

  const push = (bucket, obj) => {
    try { window.__shcap[bucket].push(obj); window.__shcap.all.push(obj); } catch(e){}
  };
  const isCap = (u) => /anti_fraud\/captcha|shopeemobile\.com\/shopee\/captcha/i.test(u);

  // --- wrap fetch ---
  const _fetch = window.fetch;
  window.fetch = async function(input, init) {
    const url = (typeof input === 'string') ? input : (input && input.url) || '';
    const method = (init && init.method) || (input && input.method) || 'GET';
    let body = init && init.body;
    const rec = {t: 'req', url, method, ts: Date.now()};
    if (body && typeof body === 'string') { rec.body = body.slice(0, 4000); }
    if (isCap(url)) {
      if (/generate/i.test(url)) push('generate', rec);
      else if (/verify/i.test(url)) push('verify', rec);
      else if (/get_config/i.test(url)) push('config', rec);
      else if (/feedback|questions/i.test(url)) push('feedback', rec);
      else push('all', rec);
    }
    const res = await _fetch.apply(this, arguments);
    if (isCap(url)) {
      try {
        const clone = res.clone();
        const txt = await clone.text();
        const entry = {t: 'resp', url, status: res.status, ts: Date.now(), body: txt.slice(0, 6000)};
        if (/generate/i.test(url)) push('generate', entry);
        else if (/verify/i.test(url)) push('verify', entry);
        else if (/get_config/i.test(url)) push('config', entry);
        else if (/feedback|questions/i.test(url)) push('feedback', entry);
        else push('all', entry);
      } catch(e){}
    }
    return res;
  };

  // --- wrap XHR ---
  const _open = XMLHttpRequest.prototype.open;
  const _send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url) {
    this.__cap_url = url; this.__cap_method = method;
    return _open.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function(body) {
    const url = this.__cap_url || '';
    if (isCap(url)) {
      const rec = {t:'xhr_req', url, method:this.__cap_method, ts:Date.now(),
                   body: (typeof body === 'string') ? body.slice(0,4000) : null};
      push('all', rec);
      this.addEventListener('load', () => {
        push('all', {t:'xhr_resp', url, status:this.status, ts:Date.now(),
                     body:(this.responseText||'').slice(0,6000)});
      });
    }
    return _send.apply(this, arguments);
  };
})();
"""


def install_captcha_hook(page):
    """Pasang hook. Panggil SETELAH goto (halaman sudah ada), SEBELUM aksi."""
    BUNDLE_JS.write_text(INJECT)
    page.add_init_script(INJECT)          # untuk navigasi berikutnya
    page.evaluate(INJECT)                 # untuk dokumen saat ini
    return True


def dump_captcha_capture(page=None, path=CAP_FILE):
    """Ambil semua yang terekam → tulis JSONL."""
    data = {}
    if page is not None:
        try:
            data = page.evaluate("() => window.__shcap || {}")
        except Exception as e:
            return f"eval error: {e}"
    with open(path, "w") as f:
        for k, arr in data.items():
            for item in (arr or []):
                f.write(json.dumps({"bucket": k, **item}, ensure_ascii=False) + "\n")
    counts = {k: len(v) for k, v in data.items() if isinstance(v, list)}
    return counts


def suggest_answer(challenge_resp: dict):
    """Placeholder: dari payload generate → usulkan koordinat/geseran.

    Struktur jawaban (dari bundle):
      klik  → captcha_top_left_x/y, captcha_box_width/height
      geser → slider_end_pos, slider_move_type
    Isi ini setelah challenge format dipahami (reverse /generate response).
    """
    return None
