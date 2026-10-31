#!/usr/bin/env python3
"""chart_stats.py — grafik harian sukses/gagal pakai PIL (tanpa matplotlib).

Bikin PNG bar chart 14 hari terakhir dari bot_store.history().

Usage:
  chart_stats.py [output.png]
"""
import sys, time
from PIL import Image, ImageDraw, ImageFont

try:
    from bot_store import history, stats
except Exception:
    def history(days=14): return []
    def stats(): return {}

BG = (18, 20, 26)
FG = (230, 232, 238)
GRID = (48, 52, 62)
GREEN = (52, 199, 123)
RED = (231, 76, 60)
BLUE = (52, 152, 219)


def _font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def make_chart(out="/root/shopee-farm/shots/stats.png", days=14):
    W, H = 900, 480
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_title = _font(26); f_lbl = _font(14); f_ax = _font(12)

    hist = history(days)
    s = stats()

    d.text((30, 20), "\U0001F4CA Shopee Farm \u2014 Statistik Harian", font=f_title, fill=FG)
    tot = s.get("total_success", 0) + s.get("total_fail", 0)
    rate = (s.get("total_success", 0) / tot * 100) if tot else 0
    sub = (f"Total: {s.get('total_success',0)} sukses / {s.get('total_fail',0)} gagal  "
           f"({rate:.1f}%)   Cache hit: {s.get('cache_hits',0)}")
    d.text((30, 56), sub, font=f_lbl, fill=(150, 155, 165))

    # area chart
    x0, y0, x1, y1 = 70, 110, W - 40, H - 60
    d.line([(x0, y0), (x0, y1), (x1, y1)], fill=GRID, width=1)

    maxv = max([max(a[1], a[2]) for a in hist] + [1])
    n = len(hist)
    bw = (x1 - x0) / max(n, 1)
    pad = bw * 0.18

    # gridlines + y labels
    for g in range(5):
        yy = y1 - (y1 - y0) * g / 4
        d.line([(x0, yy), (x1, yy)], fill=GRID, width=1)
        d.text((x0 - 32, yy - 7), str(int(maxv * g / 4)), font=f_ax, fill=(120, 125, 135))

    # bars + x labels
    for i, (day, succ, fail, _ch) in enumerate(hist):
        bx = x0 + i * bw + pad
        bwid = bw - 2 * pad
        # success (green)
        h_s = (y1 - y0) * (succ / maxv)
        if succ:
            d.rectangle([bx, y1 - h_s, bx + bwid * 0.55, y1], fill=GREEN)
        # fail (red)
        h_f = (y1 - y0) * (fail / maxv)
        if fail:
            d.rectangle([bx + bwid * 0.6, y1 - h_f, bx + bwid, y1], fill=RED)
        # tanggal (tiap 2)
        if i % 2 == 0:
            d.text((bx - 2, y1 + 6), day[5:], font=f_ax, fill=(120, 125, 135))

    # legend
    lx = x1 - 220
    d.rectangle([lx, y0 - 26, lx + 14, y0 - 12], fill=GREEN)
    d.text((lx + 20, y0 - 27), "Sukses", font=f_ax, fill=FG)
    d.rectangle([lx + 90, y0 - 26, lx + 104, y0 - 12], fill=RED)
    d.text((lx + 110, y0 - 27), "Gagal", font=f_ax, fill=FG)

    img.save(out)
    return out


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/root/shopee-farm/shots/stats.png"
    print("saved:", make_chart(out))
