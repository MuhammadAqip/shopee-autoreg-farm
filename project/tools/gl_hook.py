"""Hook WebGL / OffscreenCanvas — gegat texture puzzle captcha Shopee.

Tujuan: puzzle render di surface tertutup (bukan DOM). Coba gegat dari jalur GPU:
  - WebGLRenderingContext.texImage2D / texSubImage2D  (upload texture)
  - WebGL2RenderingContext (idem)
  - OffscreenCanvas (kalau dipakai)
  - CanvasRenderingContext2D.drawImage (sudah) + getImageData

Kalau puzzle di-upload sbg texture → kita lihat ukuran + file sumber.
"""
import json
from pathlib import Path

SHOT = Path("/root/shopee-farm/shots")
SHOT.mkdir(parents=True, exist_ok=True)

HOOK_JS = r"""
(() => {
  if (window.__glHook) return;
  window.__glHook = true;
  window.__gl = {tex: [], draw: 0, offscreen: 0, notes: []};

  const note = (o) => { try { window.__gl.tex.push(o); if(window.__gl.tex.length>200) window.__gl.tex.splice(0,100);} catch(e){} };

  // --- WebGL texImage2D (1 & 2) ---
  const hookTexImage = (proto) => {
    if (!proto || !proto.texImage2D) return;
    const orig = proto.texImage2D;
    proto.texImage2D = function() {
      try {
        const a = arguments;
        // bentuk: (target, level, internalformat, w, h, border, format, type, source)
        //   atau (target, level, internalformat, format, type, source)
        let w=null,h=null,src=null;
        if (a.length >= 9) { w=a[3]; h=a[4]; src=a[8]; }
        else { src=a[5]; if(src){w=src.width;h=src.height;} }
        if (w && h && w>60) {
          note({type:'texImage2D', w:w, h:h,
                srcType: src? (src.tagName||src.constructor&&src.constructor.name||typeof src):null,
                src: (src && src.src)? src.src.slice(0,100):null,
                t: Date.now()});
        }
      } catch(e){}
      return orig.apply(this, arguments);
    };
  };
  try { hookTexImage(WebGLRenderingContext.prototype); } catch(e){}
  try { hookTexImage(WebGL2RenderingContext.prototype); } catch(e){}

  // --- OffscreenCanvas ---
  try {
    const OC = window.OffscreenCanvas;
    if (OC) {
      const origGetCtx = OC.prototype.getContext;
      OC.prototype.getContext = function() {
        window.__gl.offscreen++;
        note({type:'offscreen', w:this.width, h:this.height, t:Date.now()});
        return origGetCtx.apply(this, arguments);
      };
    }
  } catch(e){}

  // --- drawImage (gambar yg digambar ke canvas) ---
  try {
    const draw = CanvasRenderingContext2D.prototype.drawImage;
    CanvasRenderingContext2D.prototype.drawImage = function() {
      window.__gl.draw++;
      try {
        const a=arguments; const src=a[0];
        let dw = a[7]||a.length>7? a[7]:null, dh= a[8]||a.length>8? a[8]:null;
        if (!dw && src) { dw=src.width; dh=src.height; }
        if (dw && dw>60) note({type:'drawImage', dw:dw, dh:dh,
              src:(src&&src.src)?src.src.slice(0,100):(src&&src.tagName||null), t:Date.now()});
      } catch(e){}
      return draw.apply(this, arguments);
    };
  } catch(e){}

  // --- getImageData (baca piksel canvas → sering dipakai SDK ambil challenge) ---
  try {
    const gid = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(x,y,w,h) {
      note({type:'getImageData', x:x,y:y,w:w,h:h, t:Date.now()});
      return gid.apply(this, arguments);
    };
  } catch(e){}

  return 'installed';
})();
"""


def install_gl_hook(page):
    page.add_init_script(HOOK_JS)
    try:
        return page.evaluate(HOOK_JS)
    except Exception as e:
        return f"err: {e}"


def read_gl(page):
    try:
        return page.evaluate("() => window.__gl || {}")
    except Exception as e:
        return {"error": str(e)}
