#!/usr/bin/env python3
"""sadcaptcha_client.py — client API SadCaptcha yang BENAR (fix error 400).

Endpoint resmi (base = https://www.sadcaptcha.com/api/v1):
  GET  /license/credits                       -> {"credits": N}
  POST /shopee-image-crawl-pre-analyze        -> {version, slideXProportion, skipRecommended}
  POST /shopee-image-crawl                    -> {pixelsFromSliderOrigin}  (butuh trajectory!)
  POST /puzzle                                -> {slideXProportion}

ATURAN PENTING (fix 400 yang kemarin):
  - licenseKey = QUERY PARAM, bukan header
  - /shopee-image-crawl WAJIB kirim slide_piece_trajectory (>=12 rows)
  - body image-crawl = snake_case; endpoint lain camelCase
"""
import base64
import json
import os
import re
import time
from typing import Any

import requests

BASE = "https://www.sadcaptcha.com/api/v1"
DEFAULT_TIMEOUT = 40

MIN_TRAJECTORY_ROWS = 12
SKIP_CAP = 3


class SadCaptchaError(RuntimeError):
    pass


class BadRequest(SadCaptchaError):
    """400 — body kurang lengkap / tidak ada jawaban."""


class Unauthorized(SadCaptchaError):
    """401 — API key salah / kredit habis."""


def _key(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    for p in ("/root/shopee-farm/bot_key.txt", "/root/shopee-farm/sadcaptcha_key.txt"):
        if os.path.exists(p):
            v = open(p).read().strip()
            if v:
                return v
    raise SadCaptchaError("no API key (pass explicit or write bot_key.txt)")


def _b64_strip(data: str) -> str:
    """Terima data-url atau b64 mentah -> b64 mentah tanpa prefix."""
    if "," in data[:80] and data.lstrip().startswith("data:"):
        return data.split(",", 1)[1]
    return data


def credits(key: str | None = None, timeout: int = DEFAULT_TIMEOUT) -> int:
    r = requests.get(f"{BASE}/license/credits", params={"licenseKey": _key(key)}, timeout=timeout)
    if r.status_code == 401:
        raise Unauthorized(r.text[:200])
    r.raise_for_status()
    return int(r.json().get("credits", 0))


def pre_analyze(image_b64: str, key: str | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Analisa puzzle image SEBELUM solve.

    Return: {"version": str, "slideXProportion": float, "skipRecommended": bool}
    """
    body = {"image_b64": _b64_strip(image_b64)}
    r = requests.post(
        f"{BASE}/shopee-image-crawl-pre-analyze",
        params={"licenseKey": _key(key)}, json=body, timeout=timeout,
    )
    if r.status_code == 400:
        raise BadRequest("pre-analyze 400")
    if r.status_code == 401:
        raise Unauthorized(r.text[:200])
    r.raise_for_status()
    j = r.json()
    # normalisasi (API kadang camel/snake)
    return {
        "version": j.get("version"),
        "slideXProportion": j.get("slideXProportion", j.get("slide_x_proportion")),
        "skipRecommended": bool(j.get("skipRecommended", j.get("skip_recommended", False))),
    }


def solve_image_crawl(
    puzzle_b64: str,
    piece_b64: str,
    trajectory: list[dict[str, Any]],
    key: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> int:
    """Solve arced-slide. trajectory >= 12 rows. Return pixelsFromSliderOrigin."""
    if len(trajectory) < MIN_TRAJECTORY_ROWS:
        raise BadRequest(f"trajectory too short ({len(trajectory)}<{MIN_TRAJECTORY_ROWS})")
    body = {
        "puzzle_image_b64": _b64_strip(puzzle_b64),
        "piece_image_b64": _b64_strip(piece_b64),
        "slide_piece_trajectory": trajectory,
    }
    r = requests.post(
        f"{BASE}/shopee-image-crawl",
        params={"licenseKey": _key(key)}, json=body, timeout=timeout,
    )
    if r.status_code == 400:
        raise BadRequest("image-crawl 400 — no answer / malformed body")
    if r.status_code == 401:
        raise Unauthorized(r.text[:200])
    r.raise_for_status()
    j = r.json()
    return int(j.get("pixelsFromSliderOrigin", j.get("pixels_from_slider_origin")))


def solve_puzzle(puzzle_b64: str, piece_b64: str, key: str | None = None, timeout: int = DEFAULT_TIMEOUT) -> float:
    """Puzzle slide sederhana. Return slideXProportion (0..1)."""
    body = {"puzzleImageB64": _b64_strip(puzzle_b64), "pieceImageB64": _b64_strip(piece_b64)}
    r = requests.post(f"{BASE}/puzzle", params={"licenseKey": _key(key)}, json=body, timeout=timeout)
    if r.status_code == 400:
        raise BadRequest("puzzle 400")
    if r.status_code == 401:
        raise Unauthorized(r.text[:200])
    r.raise_for_status()
    return float(r.json()["slideXProportion"])


def traj_row(pixels_from_slider_origin: int, rotation_deg: float, cx_prop: float, cy_prop: float) -> dict:
    """Bikin satu baris trajectory (format sesuai API)."""
    return {
        "pixels_from_slider_origin": int(pixels_from_slider_origin),
        "piece_rotation_angle": float(rotation_deg),
        "piece_center": {
            "proportionX": round(float(cx_prop), 4),
            "proportionY": round(float(cy_prop), 4),
        },
    }


def rotate_angle_from_style(style: str) -> float:
    """Parse 'rotate(12.5deg)' dari inline style."""
    m = re.search(r"rotate\(([-0-9.]+)deg\)", style or "")
    return float(m.group(1)) if m else 0.0


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "credits":
        print("credits:", credits())
    else:
        print(__doc__)
