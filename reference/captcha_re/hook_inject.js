
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
