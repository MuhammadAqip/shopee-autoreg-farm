"""Solver captcha slider Shopee — screenshot-region + image-diff + drag.

Kenapa screenshot-region: challenge render di iframe/shadow tertutup →
querySelectorAll gagal tembus. Jadi ambil gambar via crop layar.

Alur:
  1. Jalankan chain signup (nomor nyata) sampai captcha.
  2. Tunggu sinyal captcha: window.__shcap.generate > 0 ATAU modal terdeteksi.
  3. Screenshot region puzzle (crop area modal captcha).
  4. find_gap_x → x celah.
  5. Hitung offset → human_drag grip.
  6. Tunggu send_otp.
"""
import json
import time
from pathlib import Path

SHOT = Path("/root/shopee-farm/shots")
SHOT.mkdir(parents=True, exist_ok=True)

# area modal captcha relatif viewport (tengah layar). Tuned utk 1280x900.
PUZZLE_CLIP = {"x": 420, "y": 300, "width": 440, "height": 320}
# grip (slider handle) kira-kira di kiri-bawah gambar puzzle
GRIP_SEARCH = {"x": 380, "y": 560, "width": 120, "height": 60}


def captcha_signal(page):
    """True kalau challenge captcha kemungkinan sudah render."""
    try:
        g = page.evaluate("() => (window.__shcap && window.__shcap.generate || []).length")
    except Exception:
        g = 0
    if g:
        return True
    # fallback: cek modal teks via locator (tembus kalau bukan shadow tertutup)
    try:
        t = page.get_by_text("Verifikasi untuk melanjutkan")
        if t.count() and t.first.is_visible():
            return True
    except Exception:
        pass
    return False


def detect_modal_region(page):
    """Cari rect modal captcha via frame/locator. Return dict atau None."""
    for sel in ["iframe[src*='captcha']", "iframe", "[class*='captcha']", "[class*='verify']"]:
        try:
            loc = page.locator(sel).first
            if loc.count():
                box = loc.bounding_box()
                if box and box["width"] > 100 and box["height"] > 80:
                    return {"x": box["x"], "y": box["y"], "w": box["width"], "h": box["height"], "sel": sel}
        except Exception:
            continue
    return None


def crop_puzzle(page, tag="puzzle", clip=None):
    c = clip or PUZZLE_CLIP
    path = SHOT / f"{tag}.png"
    try:
        page.screenshot(path=str(path), clip=c)
        return str(path)
    except Exception as e:
        return None


def wait_captcha(page, timeout=30, slow=1.5):
    for _ in range(int(timeout / slow)):
        if captcha_signal(page):
            time.sleep(3)   # beri waktu render konten
            return True
        time.sleep(slow)
    return False
