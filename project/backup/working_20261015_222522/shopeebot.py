#!/usr/bin/env python3
"""Shopee Auto-Register Telegram Bot — v4 (FULL FEATURES, inline only).

Fitur:
  1. Export massal (CSV semua akun)
  2. Retry count custom (di Setting)
  3. Dashboard statistik
  4. Multi-user / ALLOWED_IDS (whitelist)
  5. Pilih proxy inline + custom proxy (tambah sendiri)
  6. Auto-farm batch (kirim list nomor)
  7. Notifikasi kredit rendah
  8. Backup akun (local / webhook / gsheet)
  9. Validasi akun (cek masih aktif)
  + Mode password Auto/Manual (custom pw)

Env: BOT_TOKEN, SADCAPTCHA_KEY, ALLOWED_IDS (opsional), OTP_CHANNEL
"""
import os, sys, json, time, asyncio, re, subprocess, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, MessageHandler, CallbackQueryHandler,
                          ContextTypes, filters)
import bot_store as BS

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SAD_KEY = os.environ.get("SADCAPTCHA_KEY", "")
ENV_ALLOWED = [x.strip() for x in os.environ.get("ALLOWED_IDS", "").split(",") if x.strip()]
PY = "/root/sniffenv/bin/python"
ROOT = "/root/shopee-farm"
SOLVER = f"{ROOT}/shopee_hold.py"
KEY_FILE = f"{ROOT}/bot_key.txt"
OTP_IN = f"{ROOT}/.otp_input"
PW_IN = f"{ROOT}/.pw_input"
STATUS = f"{ROOT}/.signup_status"
ACCOUNTS = f"{ROOT}/account_result.json"

STATE = {}
BUSY = set()
BATCH = {}   # uid -> {"queue": [phones], "idx": 0, "results": []}


# ---------- util ----------

def get_key():
    # prioritas: DB key terbaik (farm) → bot_key.txt → env
    try:
        import sadkey_db as KDB
        k = KDB.best_key()
        if k:
            return k
    except Exception:
        pass
    try:
        k = open(KEY_FILE).read().strip()
        if k:
            return k
    except Exception:
        pass
    return SAD_KEY


def set_key(k):
    open(KEY_FILE, "w").write(k.strip())


def norm_phone(s):
    s = re.sub(r"[^0-9]", "", s or "")
    if s.startswith("62"):
        s = s[2:]
    if s.startswith("0"):
        s = s[1:]
    return s


def check_credit():
    try:
        import requests
        r = requests.get(f"https://www.sadcaptcha.com/api/v1/license/credits?licenseKey={get_key()}", timeout=15)
        return r.json().get("credits")
    except Exception:
        return None


def all_proxies():
    lst = []
    try:
        lst += [l.strip() for l in open(f"{ROOT}/proxies_id_vs.txt") if l.strip()]
    except Exception:
        pass
    lst += BS.custom_proxies()
    return lst or ["http://8108c95881d0c4b2f18e__cr.id;sessttl.5:7dfd03c5eb868991@gb.vsproxy.org:10000"]


def pick_proxy():
    return random.choice(all_proxies())


def norm_pw(pw):
    pw = pw or "PASS_REDACTED"
    if not any(c.islower() for c in pw):
        pw = "a" + pw
    if not any(c.isupper() for c in pw):
        pw = pw[0].upper() + pw[1:]
    if len(pw) > 16:
        pw = pw[:16]
    if len(pw) < 8:
        pw = pw + "A1234"
    return pw


def cache_stats():
    try:
        import sqlite3
        con = sqlite3.connect(f"{ROOT}/captcha_cache.db")
        n, hits = con.execute("SELECT COUNT(*), COALESCE(SUM(hits),0) FROM puzzles").fetchone()
        con.close()
        return n, int(hits)
    except Exception:
        return 0, 0


def read_status():
    try:
        return open(STATUS).read().strip()
    except Exception:
        return ""


def read_accounts():
    try:
        out = []
        for line in open(ACCOUNTS):
            line = line.strip()
            if line.startswith("{"):
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        return out
    except Exception:
        return []


def start_solver(phone, channel, retry=3, custom_pw=""):
    for f in (OTP_IN, PW_IN, STATUS):
        try:
            os.remove(f)
        except Exception:
            pass
    proxy = pick_proxy()
    env = dict(os.environ, SADCAPTCHA_KEY=get_key())
    args = ["xvfb-run", "-a", "--server-args=-screen 0 1280x900x24",
            PY, SOLVER, phone, get_key(), proxy, channel, f"--retry={retry}"]
    if custom_pw:
        args.append(f"--pw={custom_pw}")
    return subprocess.Popen(args, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)


def is_allowed(uid):
    ids = BS.allowed_ids() or ENV_ALLOWED
    if not ids:
        return True
    return str(uid) in [str(x) for x in ids]


# ---------- keyboards ----------

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001F195 Daftar Akun Baru", callback_data="new")],
        [InlineKeyboardButton("\U0001F4E6 Auto-Farm Batch", callback_data="batch")],
        [InlineKeyboardButton("\U0001F4B3 Kredit", callback_data="cred"),
         InlineKeyboardButton("\U0001F5C3\uFE0F Cache", callback_data="cache")],
        [InlineKeyboardButton("\U0001F4CB Akun Sukses", callback_data="accounts"),
         InlineKeyboardButton("\U0001F4CA Dashboard", callback_data="dash")],
        [InlineKeyboardButton("\u2699\uFE0F Setting", callback_data="setting"),
         InlineKeyboardButton("\U0001F310 Proxy", callback_data="proxymenu")],
        [InlineKeyboardButton("\U0001F511 API Key", callback_data="keymenu"),
         InlineKeyboardButton("\U0001F331 Farm Key", callback_data="farmmenu")],
        [InlineKeyboardButton("\u2139\uFE0F Bantuan", callback_data="help")],
    ])


def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("\u2B05\uFE0F Menu", callback_data="menu")]])


def kb_setting(uid):
    u = BS.get_user(uid)
    ch, pm = u["channel"], u["pwmode"]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{'✅ ' if ch=='wa' else ''}\U0001F4F1 WhatsApp", callback_data="ch:wa"),
         InlineKeyboardButton(f"{'✅ ' if ch=='sms' else ''}\U0001F4E9 SMS", callback_data="ch:sms")],
        [InlineKeyboardButton(f"{'✅ ' if pm=='auto' else ''}\U0001F916 PW Auto", callback_data="pm:auto"),
         InlineKeyboardButton(f"{'✅ ' if pm=='manual' else ''}\u270D\uFE0F PW Manual", callback_data="pm:manual")],
        [InlineKeyboardButton(f"\U0001F501 Retry: {u['retry']}×", callback_data="retrymenu"),
         InlineKeyboardButton(f"\U0001F514 Alert: {u['credit_alert']}", callback_data="alertmenu")],
        [InlineKeyboardButton("\U0001F4BE Backup: " + u["backup_target"], callback_data="bkopts"),
         InlineKeyboardButton("\U0001F464 User Access", callback_data="usersmenu")],
        [InlineKeyboardButton("\u2B05\uFE0F Kembali", callback_data="menu")],
    ])


def setting_text(uid):
    u = BS.get_user(uid)
    ch = "WhatsApp" if u["channel"] == "wa" else "SMS"
    pm = "Auto" if u["pwmode"] == "auto" else "Manual"
    return (f"\u2699\uFE0F *Setting*\n\n\U0001F4F1 Channel: *{ch}*\n\U0001F511 Password: *{pm}*\n"
            f"\U0001F501 Retry captcha: *{u['retry']}×*\n\U0001F514 Alert kredit: *< {u['credit_alert']}*\n"
            f"\U0001F4BE Backup: *{u['backup_target']}*")


# ---------- handlers ----------

async def on_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        await update.message.reply_text("\u26D4 Akses ditolak. Hubungi admin.")
        return
    cr = check_credit(); n, hits = cache_stats(); s = BS.stats()
    txt = (f"\U0001F431 *Shopee Auto-Register Bot v4*\n\n"
           f"\U0001F4B3 Kredit: *{cr if cr is not None else '?'}*\n"
           f"\U0001F5C3\uFE0F Cache: *{n}* puzzle (*{hits}* hit)\n"
           f"\U0001F4CA Hari ini: *{s['today_success']}* sukses\n\n"
           "Semua fitur lewat tombol \u2014 gak perlu ketik command.")
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb_main())


async def cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if not is_allowed(uid):
        await q.edit_message_text("\u26D4 Akses ditolak.")
        return
    st = STATE.setdefault(uid, {"step": None})
    d = q.data
    u = BS.get_user(uid)

    async def edit(t, kb=None):
        try:
            await q.edit_message_text(t, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            await q.message.reply_text(t, parse_mode="Markdown", reply_markup=kb)

    if d == "menu":
        cr = check_credit(); n, hits = cache_stats(); s = BS.stats()
        await edit(f"\U0001F431 *Bot v4*\n\n\U0001F4B3 Kredit: *{cr if cr is not None else '?'}*\n"
                   f"\U0001F5C3\uFE0F Cache: *{n}* (*{hits}* hit)\n"
                   f"\U0001F4CA Hari ini: *{s['today_success']}* sukses", kb_main())

    elif d == "new":
        if uid in BUSY:
            await edit("\u23F3 Masih ada proses jalan.", kb_back()); return
        st["step"] = "phone"
        ch = "WhatsApp" if u["channel"] == "wa" else "SMS"
        pm = "Auto" if u["pwmode"] == "auto" else "Manual"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("\u2699\uFE0F Ganti Mode", callback_data="setting")],
            [InlineKeyboardButton("\u2B05\uFE0F Batal", callback_data="menu")]])
        await edit(f"\U0001F195 *Daftar Akun*\n\n\U0001F4F1 {ch} | \U0001F511 {pm} | \U0001F501 {u['retry']}×\n\n"
                   "\u2709\uFE0F *Kirim nomor HP* (contoh: `085729884045`)", kb)

    elif d == "batch":
        st["step"] = "batch"
        await edit("\U0001F4E6 *Auto-Farm Batch*\n\n"
                   "Kirim daftar nomor (satu per baris atau dipisah koma):\n"
                   "```\n08572xxxxxx\n08573xxxxxx\n```\n"
                   "Bot proses satu-satu otomatis. Masukin OTP tiap nomor pas diminta.", kb_back())

    elif d == "setting":
        await edit(setting_text(uid), kb_setting(uid))
    elif d.startswith("ch:"):
        BS.set_user(uid, channel=d.split(":")[1]); await edit(setting_text(uid), kb_setting(uid))
    elif d.startswith("pm:"):
        BS.set_user(uid, pwmode=d.split(":")[1]); await edit(setting_text(uid), kb_setting(uid))

    elif d == "retrymenu":
        cur = u["retry"]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{'✅ ' if cur==n else ''}{n}×", callback_data=f"retry:{n}") for n in (1, 3, 5)],
            [InlineKeyboardButton(f"{'✅ ' if cur==n else ''}{n}×", callback_data=f"retry:{n}") for n in (8, 12, 20)],
            [InlineKeyboardButton("\u2B05\uFE0F", callback_data="setting")]])
        await edit(f"\U0001F501 *Retry captcha*\n\nSekarang: *{cur}×*\nPilih jumlah maksimal percobaan:", kb)
    elif d.startswith("retry:"):
        BS.set_user(uid, retry=int(d.split(":")[1])); await edit(setting_text(uid), kb_setting(uid))

    elif d == "alertmenu":
        cur = u["credit_alert"]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{'✅ ' if cur==n else ''}< {n}", callback_data=f"alert:{n}") for n in (0, 3, 5)],
            [InlineKeyboardButton(f"{'✅ ' if cur==n else ''}< {n}", callback_data=f"alert:{n}") for n in (10, 20, 50)],
            [InlineKeyboardButton("\u2B05\uFE0F", callback_data="setting")]])
        await edit(f"\U0001F514 *Alert kredit rendah*\n\nSekarang: *< {cur}*\n(0 = nonaktif)", kb)
    elif d.startswith("alert:"):
        BS.set_user(uid, credit_alert=int(d.split(":")[1])); await edit(setting_text(uid), kb_setting(uid))

    elif d == "bkopts":
        cur = u["backup_target"]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{'✅ ' if cur=='local' else ''}\U0001F4C1 Local CSV", callback_data="bk:local")],
            [InlineKeyboardButton(f"{'✅ ' if cur=='webhook' else ''}\U0001F517 Webhook", callback_data="bk:webhook")],
            [InlineKeyboardButton(f"{'✅ ' if cur=='gsheet' else ''}\U0001F4CA Google Sheet", callback_data="bk:gsheet")],
            [InlineKeyboardButton("\u2B05\uFE0F", callback_data="setting")]])
        await edit(f"\U0001F4BE *Backup target*\n\nSekarang: *{cur}*\n(webhook/gsheet: kirim URL setelah pilih)", kb)
    elif d.startswith("bk:"):
        t = d.split(":")[1]
        BS.set_user(uid, backup_target=t)
        if t in ("webhook", "gsheet"):
            st["step"] = "bkurl"
            await edit(f"\U0001F517 Kirim URL backup ({t}):", kb_back())
        else:
            await edit(setting_text(uid), kb_setting(uid))

    elif d == "usersmenu":
        ids = BS.allowed_ids()
        lst = "\n".join(f"• `{i}`" for i in ids) or "_(kosong = semua boleh)_"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("\u2795 Tambah User", callback_data="useradd")],
            [InlineKeyboardButton("\U0001F5D1\uFE0F Hapus Semua", callback_data="userclear")],
            [InlineKeyboardButton("\u2B05\uFE0F", callback_data="setting")]])
        await edit(f"\U0001F464 *User Access (whitelist)*\n\n{lst}\n\n"
                   "Kalau ada isi, cuma ID itu yang boleh pakai bot.", kb)
    elif d == "useradd":
        st["step"] = "useradd"
        await edit("\u2795 Kirim Telegram user ID yang diizinkan\n(cek via @userinfobot)", kb_back())
    elif d == "userclear":
        BS.clear_allowed(); await edit("\U0001F5D1\uFE0F Whitelist dibersihin (semua boleh).", kb_back())

    elif d == "proxymenu":
        cps = BS.custom_proxies()
        lst = "\n".join(f"{i+1}. `{p[:48]}`" for i, p in enumerate(cps)) or "_(belum ada custom)_"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("\u2795 Tambah Proxy", callback_data="padd")],
            [InlineKeyboardButton("\U0001F5D1\uFE0F Hapus Semua", callback_data="pclear")],
            [InlineKeyboardButton("\U0001F310 Tes Rotasi", callback_data="ptest")],
            [InlineKeyboardButton("\u2B05\uFE0F Menu", callback_data="menu")]])
        await edit(f"\U0001F310 *Proxy*\n\n*Custom:*\n{lst}\n\nTotal rotasi: *{len(all_proxies())}* proxy", kb)
    elif d == "padd":
        st["step"] = "padd"
        await edit("\u2795 Kirim proxy:\n`http://user:pass@host:port`\n\n"
                   "Atau `host:port` (tanpa auth). Satu per pesan.", kb_back())
    elif d == "pclear":
        BS.clear_proxies(); await edit("\U0001F5D1\uFE0F Custom proxy dihapus.", kb_back())
    elif d == "ptest":
        lst = all_proxies()
        await edit(f"\U0001F310 Total *{len(lst)}* proxy siap rotasi.\nSample: `{lst[0][:60]}`", kb_back())

    elif d == "cred":
        cr = check_credit()
        warn = ""
        if cr is not None and cr < u["credit_alert"]:
            warn = f"\n\n\u26A0\uFE0F *Kredit rendah!* (< {u['credit_alert']})"
        await edit(f"\U0001F4B3 *Kredit SadCaptcha*\n\nSisa: *{cr if cr is not None else '?'}*{warn}", kb_back())

    elif d == "cache":
        n, hits = cache_stats()
        try:
            out = subprocess.run([PY, f"{ROOT}/cache_cli.py", "top"], capture_output=True, text=True, timeout=15).stdout
        except Exception:
            out = "(gagal)"
        await edit(f"\U0001F5C3\uFE0F *Cache*\nEntries: *{n}* | Hits: *{hits}* (\u2248${hits*0.002:.3f})\n\n"
                   f"```\n{out[:500]}\n```", kb_back())

    elif d == "dash":
        s = BS.stats(); n, hits = cache_stats(); accs = read_accounts()
        tot = s["total_success"] + s["total_fail"]
        rate = (s["total_success"] / tot * 100) if tot else 0
        await edit(
            "\U0001F4CA *Dashboard*\n\n"
            f"\u2705 Sukses total: *{s['total_success']}*\n"
            f"\u274C Gagal total: *{s['total_fail']}*\n"
            f"\U0001F4C8 Success rate: *{rate:.1f}%*\n\n"
            f"\U0001F4C5 *Hari ini:* {s['today_success']} sukses / {s['today_fail']} gagal\n"
            f"\U0001F5C3\uFE0F Cache hit: *{s['cache_hits']}*\n"
            f"\U0001F4BE Total akun terdaftar: *{len(accs)}*",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("\U0001F4C8 Grafik Harian", callback_data="chart")],
                [InlineKeyboardButton("\u2B05\uFE0F Menu", callback_data="menu")]]))

    elif d == "chart":
        try:
            import chart_stats as CS
            p = CS.make_chart(f"{ROOT}/shots/stats.png", 14)
            await q.message.reply_photo(open(p, "rb"),
                                        caption="\U0001F4C8 Statistik 14 hari terakhir")
        except Exception as e:
            await edit(f"\u274C Gagal bikin grafik: {e}", kb_back())

    elif d == "accounts":
        accs = read_accounts()
        if not accs:
            await edit("\U0001F4CB Belum ada akun.", kb_back())
        else:
            lines = [f"\U0001F464 `{a.get('phone','?')}` uid `{a.get('user_id','?')}`" for a in accs[-8:]]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("\U0001F4E6 Export CSV Semua", callback_data="export")],
                [InlineKeyboardButton("\U0001F50D Validasi Semua", callback_data="validateall")],
                [InlineKeyboardButton("\u2B05\uFE0F Menu", callback_data="menu")]])
            await edit(f"\U0001F4CB *Akun sukses ({len(accs)}):*\n\n" + "\n".join(lines) +
                       "\n\n_Ketik nomor buat detail._", kb)

    elif d == "export":
        try:
            import backup_account as BA
            p = BA.export_all_csv()
            await q.message.reply_document(open(p, "rb"), filename=os.path.basename(p),
                                           caption=f"\U0001F4E6 Export {len(read_accounts())} akun")
        except Exception as e:
            await edit(f"\u274C Export gagal: {e}", kb_back())

    elif d == "validateall":
        accs = read_accounts()
        if not accs:
            await edit("Belum ada akun.", kb_back()); return
        await edit(f"\U0001F50D Validasi *{len(accs)}* akun... (proses)")
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, _validate_all, accs)
        ok = sum(1 for r in res if r["ok"])
        okc = "\U0001F7E2"; noc = "\U0001F534"
        lines = [f"{okc if r['ok'] else noc} `{r['phone']}` {'AKTIF' if r['ok'] else r['reason'][:30]}" for r in res[:15]]
        await edit(f"\U0001F50D *Validasi akun*\n\n\u2705 Aktif: *{ok}* / {len(res)}\n\n" + "\n".join(lines), kb_back())

    elif d == "keymenu":
        cur = get_key()
        masked = cur[:6] + "..." + cur[-4:] if len(cur) > 12 else "?"
        st["step"] = "setkey"
        await edit(f"\U0001F511 *API Key*\n\nAktif: `{masked}`\nKredit: *{check_credit()}*\n\nKirim key baru:", kb_back())

    elif d == "farmmenu":
        try:
            import sadkey_db as KDB
            tot, n = KDB.total_credits()
        except Exception:
            tot, n = 0, 0
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("\U0001F331 Farm 2 Akun", callback_data="farm:2"),
             InlineKeyboardButton("3 Akun", callback_data="farm:3")],
            [InlineKeyboardButton("5 Akun", callback_data="farm:5"),
             InlineKeyboardButton("10 Akun", callback_data="farm:10")],
            [InlineKeyboardButton("\U0001F504 Sync Key Baru", callback_data="farmsync"),
             InlineKeyboardButton("\U0001F4CB List Key", callback_data="farmlist")],
            [InlineKeyboardButton("\u2B05\uFE0F Menu", callback_data="menu")]])
        await edit(f"\U0001F331 *Farm SadCaptcha Key*\n\n"
                   f"\U0001F5C3\uFE0F DB: *{n}* key (*{tot}* credits)\n\n"
                   "Pilih jumlah akun buat di-farm.\n"
                   "Bot jalanin full-auto: audio captcha → verify → login → ambil API key.\n"
                   "\u23F3 ~2-4 menit per akun.", kb)

    elif d == "farmsync":
        try:
            import sadkey_db as KDB
            added, total = KDB.sync_from_farm()
            KDB.refresh()
            tot, n = KDB.total_credits()
            k = KDB.sync_bot_key()
            await edit(f"\u2705 *Sync selesai*\n\n+{added} key baru\nDB: {n} key ({tot} credits)\n"
                       f"Bot pakai: `{k[:8] + '...' if k else 'none'}`", kb_back())
        except Exception as e:
            await edit(f"\u274C Sync gagal: {e}", kb_back())

    elif d == "farmlist":
        try:
            import sadkey_db as KDB
            keys = KDB.list_keys()
            if not keys:
                await edit("\U0001F4CB DB kosong. Sync dulu.", kb_back()); return
            lines = [f"\U0001F511 `{k['key'][:12]}...` {k.get('credits')}cr" for k in keys[-12:]]
            await edit(f"\U0001F4CB *Key DB ({len(keys)}):*\n\n" + "\n".join(lines), kb_back())
        except Exception as e:
            await edit(f"\u274C {e}", kb_back())

    elif d.startswith("farm:"):
        n = int(d.split(":")[1])
        if uid in BUSY:
            await edit("\u23F3 Masih ada proses jalan.", kb_back()); return
        BUSY.add(uid)
        msg = q.message
        await edit(f"\U0001F331 *Farm {n} akun dimulai...*\n\n\u23F3 Proses...", kb_back())
        asyncio.create_task(farm_worker(msg, uid, n))

    elif d == "help":
        await edit("\u2139\uFE0F *Cara Pakai*\n\n"
                   "\U0001F195 *Daftar Akun*: kirim nomor \u2192 OTP \u2192 jadi\n"
                   "\U0001F4E6 *Auto-Farm*: kirim banyak nomor sekaligus\n"
                   "\U0001F4CA *Dashboard*: statistik sukses/gagal\n"
                   "\U0001F310 *Proxy*: tambah proxy custom sendiri\n"
                   "\u2699\uFE0F *Setting*: channel, mode PW, retry, alert, backup\n"
                   "\U0001F331 *Farm Key*: farm API key SadCaptcha otomatis\n"
                   "\U0001F511 *API Key*: ganti SadCaptcha key\n\n"
                   "Data akun: username/pass/nomor/userid/fp/device/cookie.", kb_back())


def _validate_all(accs):
    import validate_account as VA
    out = []
    for a in accs:
        r = VA.validate(a.get("cookie", ""))
        out.append({"phone": a.get("phone", "?"), **r})
    return out


async def on_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handler command lama (/start /help dll) -> arahin ke menu inline."""
    uid = update.effective_user.id
    if not is_allowed(uid):
        await update.message.reply_text("\u26D4 Akses ditolak.")
        return
    STATE.setdefault(uid, {"step": None})
    cr = check_credit(); n, hits = cache_stats(); s = BS.stats()
    txt = (f"\U0001F431 *Shopee Auto-Register Bot v4*\n\n"
           f"\U0001F4B3 Kredit: *{cr if cr is not None else '?'}*\n"
           f"\U0001F5C3\uFE0F Cache: *{n}* puzzle (*{hits}* hit)\n"
           f"\U0001F4CA Hari ini: *{s['today_success']}* sukses\n\n"
           "Semua fitur lewat tombol di bawah \u2014 gak perlu ketik command.")
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb_main())


async def send_result(update, a):
    txt = ("\u2705 *AKUN SHOPEE JADI*\n\n"
           f"Username   : `{a.get('username','-')}`\n"
           f"Password   : `{a.get('password','-')}`\n"
           f"Nomor      : `{a.get('phone','-')}`\n"
           f"UserId     : `{a.get('user_id','-') or '-'}`\n"
           f"Fingerprint: `{a.get('fingerprint','-') or '-'}`\n"
           f"Device ID  : `{a.get('device_id','-') or '-'}`\n\n"
           "\U0001F36A *Cookie:*\n"
           f"`{a.get('cookie','-')}`")
    try:
        await update.message.reply_text(txt, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(txt[:1000])
    try:
        pth = f"{ROOT}/shots/acc_{a.get('phone','x')}.txt"
        with open(pth, "w") as f:
            f.write(f"Username: {a.get('username','')}\nPassword: {a.get('password','')}\n"
                    f"Nomor: {a.get('phone','')}\nUserId: {a.get('user_id','')}\n"
                    f"Fingerprint: {a.get('fingerprint','')}\nDevice ID: {a.get('device_id','')}\n"
                    f"Cookie: {a.get('cookie','')}\n")
        await update.message.reply_document(open(pth, "rb"), filename=f"shopee_{a.get('phone','x')}.txt")
    except Exception:
        pass


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        await update.message.reply_text("\u26D4 Akses ditolak.")
        return
    st = STATE.setdefault(uid, {"step": None})
    text = (update.message.text or "").strip()
    step = st.get("step")
    u = BS.get_user(uid)

    if step == "setkey":
        if len(text) < 16:
            await update.message.reply_text("\u274C Key kekependekan.", reply_markup=kb_back()); return
        set_key(text); cr = check_credit(); st["step"] = None
        await update.message.reply_text(f"\u2705 Key diganti. Kredit: *{cr}*", parse_mode="Markdown", reply_markup=kb_main())
        return

    if step == "bkurl":
        open(f"{ROOT}/.backup_url", "w").write(text)
        st["step"] = None
        await update.message.reply_text("\u2705 URL backup disimpan.", reply_markup=kb_main())
        return

    if step == "useradd":
        ok = BS.add_allowed(text); st["step"] = None
        await update.message.reply_text(f"{'✅ Ditambah' if ok else '⚠️ Sudah ada/keliru'}: `{text}`",
                                        parse_mode="Markdown", reply_markup=kb_main())
        return

    if step == "padd":
        p = text if text.startswith("http") else "http://" + text
        ok = BS.add_proxy(p); st["step"] = None
        await update.message.reply_text(f"{'✅ Proxy ditambah' if ok else '⚠️ Sudah ada'}\n`{p[:60]}`",
                                        parse_mode="Markdown", reply_markup=kb_main())
        return

    if step == "batch":
        nums = [norm_phone(x) for x in re.split(r"[\s,;]+", text) if x.strip()]
        nums = [n for n in nums if 8 <= len(n) <= 15]
        if not nums:
            await update.message.reply_text("\u274C Gak ada nomor valid."); return
        st["step"] = None
        BATCH[uid] = {"queue": nums, "idx": 0, "results": [],
                      "channel": u["channel"], "retry": u["retry"]}
        await update.message.reply_text(f"\U0001F4E6 Batch *{len(nums)}* nomor dimulai...", parse_mode="Markdown")
        asyncio.create_task(batch_worker(update, uid))
        return

    if step == "batch_otp":
        if not re.fullmatch(r"\d{4,8}", text):
            await update.message.reply_text("\u274C OTP harus angka."); return
        open(OTP_IN, "w").write(text)
        pw = u.get("custom_pw") or "PASS_REDACTED"
        open(PW_IN, "w").write(pw)
        st["step"] = "batch_wait"
        await update.message.reply_text("\u2705 OTP diterima. Daftar...\n\u23F3")
        return

    if step is None:
        cand = norm_phone(text)
        if re.fullmatch(r"8\d{7,13}", cand):
            for a in reversed(read_accounts()):
                if a.get("phone") == cand:
                    await send_result(update, a); return

    if step == "phone":
        phone = norm_phone(text)
        if len(phone) < 8 or len(phone) > 15:
            await update.message.reply_text("\u274C Nomor gak valid."); return
        cr = check_credit(); n, hits = cache_stats()
        if cr is not None and cr <= 0 and hits == 0:
            await update.message.reply_text("\u274C Kredit habis & cache kosong.", reply_markup=kb_main()); return
        BUSY.add(uid); st["step"] = None; st["phone"] = phone
        BS.bump("attempt")
        pr = start_solver(phone, u["channel"], u["retry"])
        msg = await update.message.reply_text(
            f"\U0001F680 *Register `{phone}`*\n\U0001F4F1 {('WhatsApp' if u['channel']=='wa' else 'SMS')} | \U0001F501 {u['retry']}×\n"
            "Buka form → captcha... (1-2 mnt)", parse_mode="Markdown")
        asyncio.create_task(poll_otp(update, uid, phone, pr, msg))
        return

    if step == "otp":
        if not re.fullmatch(r"\d{4,8}", text):
            await update.message.reply_text("\u274C OTP harus angka."); return
        open(OTP_IN, "w").write(text); st["step"] = None
        if u["pwmode"] == "manual" and not st.get("pw"):
            st["step"] = "password"
            await update.message.reply_text("\u2705 OTP diterima.\n\n\u270D\uFE0F *Kirim password* (min 8, ada BESAR+kecil):")
            return
        pw = u.get("custom_pw") or "PASS_REDACTED"
        open(PW_IN, "w").write(pw)
        await update.message.reply_text("\u2705 OTP diterima. Daftar...\n\u23F3")
        asyncio.create_task(poll_finish(update, uid, st.get("phone", ""), pw))
        return

    if step == "password":
        if len(text) < 8 or not any(c.isupper() for c in text):
            await update.message.reply_text("\u274C Perlu min 8 char + 1 BESAR."); return
        pw = norm_pw(text); open(PW_IN, "w").write(pw)
        st["pw"] = pw; st["step"] = None
        await update.message.reply_text("\u2705 Password diset. Daftar...\n\u23F3")
        asyncio.create_task(poll_finish(update, uid, st.get("phone", ""), pw))
        return

    await update.message.reply_text("\U0001F431 Pakai tombol di bawah.", reply_markup=kb_main())


# ---------- pollers ----------

async def poll_otp(update, uid, phone, pr, msg):
    try:
        waited = 0
        while waited < 220:
            s = read_status()
            if "WAITING_OTP" in s:
                STATE[uid]["step"] = "otp"
                await msg.edit_text(f"\u2705 *Captcha tembus \u2014 {phone}*\n\n\U0001F4E9 Kirim *OTP* sekarang.",
                                    parse_mode="Markdown", reply_markup=kb_back())
                return
            if pr.poll() is not None:
                await msg.edit_text(f"\u274C Solver berhenti \u2014 {phone}\n`{s}`", parse_mode="Markdown")
                BS.bump("fail"); return
            await asyncio.sleep(4); waited += 4
        STATE[uid]["step"] = "otp"
        await msg.edit_text(f"\u23F3 `{phone}` \u2014 kirim OTP.", parse_mode="Markdown")
    finally:
        BUSY.discard(uid)


async def _get_acc(phone):
    for a in reversed(read_accounts()):
        if a.get("phone") == phone:
            return a
    return None


async def handle_finish(update, uid, phone):
    acc = await _get_acc(phone)
    if acc:
        BS.bump("success")
        await update.message.reply_text(f"\U0001F389 *{phone}* berhasil!")
        await send_result(update, acc)
        try:
            u = BS.get_user(uid)
            import backup_account as BA
            url = ""
            try:
                url = open(f"{ROOT}/.backup_url").read().strip()
            except Exception:
                pass
            BA.backup(acc, u["backup_target"], url)
        except Exception:
            pass
        return acc
    BS.bump("fail")
    final = read_status()
    try:
        shot = subprocess.run(["ls", "-t", f"{ROOT}/shots/"], capture_output=True, text=True).stdout.splitlines()
        shot = [x for x in shot if phone in x]
        if shot:
            await update.message.reply_photo(open(f"{ROOT}/shots/{shot[0]}", "rb"),
                                             caption=f"\U0001F4F8 {phone} \u2014 {final[-60:]}")
    except Exception:
        pass
    await update.message.reply_text(f"\u26A0\uFE0F *{phone}* selesai. Status: `{final[-80:]}`", parse_mode="Markdown")
    return None


async def poll_finish(update, uid, phone, pw):
    waited = 0
    while waited < 100:
        s = read_status()
        if "SUCCESS" in s or "DONE" in s:
            break
        if "OTP_WRONG" in s:
            STATE[uid]["step"] = "otp"
            await update.message.reply_text("\u274C OTP salah/expired. Kirim ulang."); return
        await asyncio.sleep(4); waited += 4
    await handle_finish(update, uid, phone)


async def batch_worker(update, uid):
    b = BATCH.get(uid)
    if not b:
        return
    while b["idx"] < len(b["queue"]):
        phone = b["queue"][b["idx"]]
        n_done = b["idx"]; total = len(b["queue"])
        status_msg = await update.message.reply_text(
            f"\U0001F4E6 *Batch [{n_done+1}/{total}]* \u2014 `{phone}`\n\n\u23F3 Solve captcha...",
            parse_mode="Markdown")
        BUSY.add(uid)
        BS.bump("attempt")
        pr = start_solver(phone, b["channel"], b["retry"])
        got_otp = False; waited = 0
        while waited < 220:
            s = read_status()
            if "WAITING_OTP" in s:
                got_otp = True; break
            if pr.poll() is not None:
                break
            await asyncio.sleep(4); waited += 4
        if got_otp:
            STATE[uid]["step"] = "batch_otp"
            await status_msg.edit_text(
                f"\U0001F4E6 *Batch [{n_done+1}/{total}]* \u2014 `{phone}`\n\n"
                "\u2705 Captcha tembus! \U0001F4E9 *Kirim OTP nomor ini sekarang.*", parse_mode="Markdown")
            for _ in range(180):
                if STATE[uid].get("step") != "batch_otp":
                    break
                await asyncio.sleep(2)
            waited = 0
            while waited < 100:
                s = read_status()
                if "SUCCESS" in s or "DONE" in s:
                    break
                await asyncio.sleep(4); waited += 4
            acc = await _get_acc(phone)
            if acc:
                BS.bump("success"); b["results"].append(("ok", phone))
                await update.message.reply_text(f"\U0001F389 `{phone}` \u2705 berhasil!")
                await send_result(update, acc)
                try:
                    u = BS.get_user(uid)
                    import backup_account as BA
                    BA.backup(acc, u["backup_target"])
                except Exception:
                    pass
            else:
                BS.bump("fail"); b["results"].append(("fail", phone))
                await update.message.reply_text(f"\u274C `{phone}` gagal.", parse_mode="Markdown")
        else:
            BS.bump("fail"); b["results"].append(("fail", phone))
            await status_msg.edit_text(f"\U0001F4E6 [{n_done+1}/{total}] `{phone}` \u274C captcha gagal.", parse_mode="Markdown")
        BUSY.discard(uid)
        b["idx"] += 1
    ok = sum(1 for r in b["results"] if r[0] == "ok")
    okm = "\u2705"; nom = "\u274C"
    lines = [f"{okm if r[0]=='ok' else nom} `{r[1]}`" for r in b["results"]]
    await update.message.reply_text(
        f"\U0001F4E6 *Batch Selesai*\n\n\u2705 Sukses: *{ok}* / {len(b['results'])}\n\n" + "\n".join(lines),
        parse_mode="Markdown", reply_markup=kb_main())
    BATCH.pop(uid, None)


async def farm_worker(msg, uid, count):
    """jalanin farm_batch + live update ke telegram."""
    import subprocess, json as _json
    status_file = "/root/sadfarm/farm_status.json"
    log_file = "/tmp/bot_farm.log"
    try: os.remove(status_file)
    except Exception: pass
    proc = subprocess.Popen(
        ["/root/sniffenv/bin/python", "/root/sadfarm/farm_batch.py", "--count", str(count)],
        stdout=open(log_file, "w"), stderr=subprocess.STDOUT)
    last = ""
    # kirim pesan status baru yang bisa di-edit
    try:
        status_msg = await msg.reply_text("\U0001F331 *Farm dimulai...*", parse_mode="Markdown")
    except Exception:
        status_msg = msg
    while proc.poll() is None:
        try:
            st = _json.load(open(status_file))
            done, ok, fail, target = st.get("done", 0), st.get("ok", 0), st.get("fail", 0), st.get("target", count)
            card = st.get("results", [])
            cur = card[-1] if card else None
            bar = "\u2588" * done + "\u2591" * max(0, target - done)
            line = ""
            if done < target:
                line = f"\n\n\u23F3 Proses akun {done+1}/{target}..."
            txt = (f"\U0001F331 *Farm {target} akun*\n\n`{bar}` {done}/{target}\n"
                   f"\u2705 {ok}  \u274C {fail}{line}")
            if txt != last:
                try:
                    await status_msg.edit_text(txt, parse_mode="Markdown")
                except Exception:
                    pass
                last = txt
        except Exception:
            pass
        await asyncio.sleep(8)

    # final
    try:
        st = _json.load(open(status_file))
        ok, fail, target = st.get("ok", 0), st.get("fail", 0), st.get("target", count)
        results = st.get("results", [])
        lines = []
        for r in results:
            if r.get("apikey"):
                lines.append(f"\u2705 `{r['apikey'][:10]}...` {r.get('credits')}cr")
            else:
                lines.append("\u274C gagal")
        # sync ke DB
        try:
            import sadkey_db as KDB
            added, total = KDB.sync_from_farm()
            KDB.sync_bot_key()
            extra = f"\n\n\U0001F504 Sync: +{added} key → DB"
        except Exception:
            extra = ""
        await msg.reply_text(
            f"\U0001F331 *Farm selesai*\n\n\u2705 Sukses: *{ok}* / {target}\n\u274C Gagal: *{fail}*{extra}\n\n"
            + "\n".join(lines), parse_mode="Markdown", reply_markup=kb_main())
    except Exception as e:
        await msg.reply_text(f"\U0001F331 Farm selesai (err baca status: {e})", reply_markup=kb_main())
    BUSY.discard(uid)


def main():
    if not BOT_TOKEN:
        print("ERROR: set BOT_TOKEN"); sys.exit(1)
    if not SAD_KEY:
        print("ERROR: set SADCAPTCHA_KEY"); sys.exit(1)
    app = Application.builder().token(BOT_TOKEN).build()
    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler(["start", "help", "menu", "setting", "credits", "cache", "accounts", "key"], on_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print("Bot v4 jalan.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
