"""Shopee Signup Farm — runner lengkap.

Pipeline per-akun:
  1. Browser non-headless (Xvfb) + cookie bahasa (modal fix)
  2. Proxy residential ID (dari file)
  3. goto signup → dismiss modal bahasa
  4. fill nomor → submit → Setuju (TOS)
  5. tunggu captcha (anti_fraud) → crop puzzle → gap detect → drag solve → verify
  6. tunggu OTP → tulis nomor ke file output (buat ambil SMS) → lanjut akun berikut

Env:
  SHOPEE_PHONES   : file berisi 1 nomor per baris (atau comma list)
  SHOPEE_PROXIES  : file proxy (http://user:pass@host:port)
  SHOPEE_XVFB     : "1" -> pakai xvfb-run (non-headless)

Jalankan:
  xvfb-run -a --server-args="-screen 0 1280x900x24" \
    SHOPEE_PHONES=phones.txt SHOPEE_PROXIES=proxies.txt python3 farm_run.py
"""
import os, sys, time, json, random, tempfile
from pathlib import Path

sys.path.insert(0, "/root/shopee-farm")
from playwright.sync_api import sync_playwright
from tools.signup_driver import fill_field, click_submit, JS_CLICK_AGREE
from tools.captcha_flow import wait_captcha
from tools.captcha_hook import install_captcha_hook
from tools.ui_solver import human_drag, find_captcha_elements

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
ROOT = Path("/root/shopee-farm")
OUT = ROOT / "farm_out"
OUT.mkdir(exist_ok=True)
SHOTS = ROOT / "shots"
SHOTS.mkdir(exist_ok=True)


def load_lines(path):
    if not path or not Path(path).exists():
        return []
    return [l.strip() for l in Path(path).read_text().splitlines() if l.strip() and not l.startswith("#")]


def parse_proxy(px):
    if not px:
        return None
    cred, host = px.split("@")
    user = cred.split("://")[1].split(":")[0]
    pwd = cred.split(":")[-1]
    return {"server": "http://" + host, "username": user, "password": pwd}


def attempt_account(pw, phone, proxy, idx):
    """Satu percobaan signup. Return dict hasil."""
    result = {"phone": phone, "stage": "init", "ok": False}
    proxy_cfg = parse_proxy(proxy)
    b = pw.chromium.launch(headless=False,
                           args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    kwargs = dict(user_agent=UA, locale="id-ID",
                  extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
                  viewport={"width": 1280, "height": 900})
    if proxy_cfg:
        kwargs["proxy"] = proxy_cfg
    c = b.new_context(**kwargs)
    c.add_cookies([{"name": "shopee_webLanguage", "value": "id",
                    "domain": ".shopee.co.id", "path": "/"}])
    p = c.new_page()
    net = []
    def _resp(r):
        if any(k in r.url for k in ("get_settings_v2", "send_otp", "anti_fraud")):
            try:
                net.append({"status": r.status, "url": r.url.split("/api/")[-1][:60],
                            "body": r.text()[:300]})
            except Exception:
                pass
    p.on("response", _resp)
    try:
        # 1. buka halaman
        p.goto("https://shopee.co.id/buyer/signup", wait_until="domcontentloaded", timeout=45000)
        try:
            p.wait_for_load_state("networkidle", timeout=18000)
        except Exception:
            pass
        time.sleep(3)
        install_captcha_hook(p)
        result["stage"] = "loaded"

        # 2. dismiss modal bahasa (kuat: tunggu modal hilang, klik berulang)
        def modal_visible():
            try:
                return p.evaluate("""() => {
                    const b=document.body.innerText||'';
                    return /Pilih bahasa Anda/i.test(b);
                }""")
            except Exception:
                return False
        for _ in range(8):
            if not modal_visible():
                break
            clicked = False
            for sel in ["button:has-text('Bahasa Indonesia')",
                        "text=Bahasa Indonesia",
                        "[class*=language] button"]:
                try:
                    loc = p.locator(sel).first
                    if loc.count() and loc.is_visible():
                        loc.click(timeout=2500); clicked = True; break
                except Exception:
                    continue
            time.sleep(1.5)
            if not clicked:
                try:
                    p.keyboard.press("Escape"); time.sleep(0.8)
                except Exception:
                    pass
        time.sleep(1)

        # 3. fill + submit
        fill_field(p, 0, phone)
        time.sleep(1)
        click_submit(p)
        time.sleep(3)
        result["stage"] = "submitted"

        # 4. TOS Setuju
        for _ in range(5):
            try:
                if p.evaluate(JS_CLICK_AGREE):
                    break
            except Exception:
                pass
            time.sleep(1)

        # 5. tunggu captcha / cek error / cek OTP
        t0 = time.time()
        state = "wait"
        while time.time() - t0 < 25:
            err = p.evaluate("""() => {
                const b = document.body.innerText || '';
                if (/kode verifikasi|Kode Verifikasi/i.test(b)) return 'otp';
                if (/Terjadi kesalahan|telah terjadi kesalahan/i.test(b)) return 'error';
                return '';
            }""")
            if err == "otp":
                state = "otp"; break
            if err == "error":
                state = "error"; break
            if wait_captcha(p, timeout=2):
                state = "captcha"; break
            time.sleep(1)

        result["stage"] = state

        if state == "captcha":
            # 6. coba solve slider
            p.screenshot(path=str(SHOTS / f"farm{idx}_captcha.png"))
            elems = find_captcha_elements(p)
            result["captcha_elems"] = elems
            # TODO: gap detect + drag (butuh rect presisi — lihat SOLVER_FINAL_STATUS.md)
            result["note"] = "captcha visible; solver needs precise rect (see docs)"
        elif state == "otp":
            p.screenshot(path=str(SHOTS / f"farm{idx}_otp.png"))
            result["ok"] = True
            result["note"] = "OTP screen reached — input SMS code"
        elif state == "error":
            result["note"] = "server rejected (rate-limit/IP/number)"

        result["network"] = net[-6:]
    except Exception as e:
        result["note"] = f"exception: {e.__class__.__name__}: {e}"
    finally:
        try:
            p.screenshot(path=str(SHOTS / f"farm{idx}_final.png"))
        except Exception:
            pass
        b.close()
    return result


def main():
    phones = []
    if os.environ.get("SHOPEE_PHONES"):
        phones = load_lines(os.environ["SHOPEE_PHONES"])
    if not phones:
        print("no SHOPEE_PHONES file"); return
    proxies = load_lines(os.environ.get("SHOPEE_PROXIES"))
    if not proxies:
        proxies = [None]

    results = []
    for i, phone in enumerate(phones):
        phone = phone.lstrip("+").lstrip("0")
        if phone.startswith("62"):
            phone = phone[2:]
        px = random.choice(proxies)
        print(f"[{i+1}/{len(phones)}] {phone} via {px or 'direct'}")
        with sync_playwright() as pw:
            res = attempt_account(pw, phone, px, i)
        results.append(res)
        print("   ->", json.dumps({k: v for k, v in res.items() if k != 'network'}, ensure_ascii=False))
        time.sleep(random.uniform(8, 20))

    (OUT / "farm_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"\nsaved {OUT/'farm_results.json'}")
    ok = [r for r in results if r.get("ok")]
    print(f"OTP reached: {len(ok)}/{len(results)}")


if __name__ == "__main__":
    main()
