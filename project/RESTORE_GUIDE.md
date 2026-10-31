# 📦 SHOPEE FARM — BACKUP & RESTORE GUIDE

Backup dibuat: 2026-10-16 17:15 CST
Source VPS: /root/shopee-farm + /root/sadfarm

================================================================================
## ISI BACKUP
================================================================================

- `shopee-farm/`  → project utama (156 .py, 49 laporan .md, SDK, tools)
- `sadfarm/`      → farm key SadCaptcha (feed key pool)

Termasuk KRITIS:
  - shopeebot.py        (bot Telegram @tokn_aiBot)
  - shopee_hold.py      (solver inti — 49KB)
  - key_manager.py      (rotasi + failover key)
  - phone_reputation.py (pre-check anti-LIMIT)
  - captcha_cache.py    (cache v2 content-match)
  - farm_production.py  (scheduler produksi)
  - accounts.db + accounts* (hasil akun)
  - captcha_cache.db    (161+ puzzle cache)
  - bot_key.txt, .bot.env (kredensial — JAGA RAHASIA)
  - toolkit VM reverse (vm_*.py, vm_bytecode_FULL.json)
  - tools/ (solver, gap detect, signup driver)
  - sdk/ (SDK Shopee + sadcaptcha_ref)

================================================================================
## CARA RESTORE DI VPS BARU
================================================================================

### 1. Extract
```bash
cd /root
unzip shopee-farm_backup_YYYYMMDD_HHMM.zip
# → hasil: /root/shopee-farm  /root/sadfarm
```

### 2. Python env (butuh conda/py 3.12 + libs)
```bash
# pakai env yg sama kalau ada, atau bikin baru:
python3 -m venv /root/sniffenv
/root/sniffenv/bin/pip install playwright requests telegram-python-bot \
    opencv-python numpy aiohttp beautifulsoup4 lxml pycryptodome
/root/sniffenv/bin/playwright install chromium
```
CATATAN: path interpreter yg dipakai = `/root/sniffenv/bin/python`

### 3. Dependensi sistem (headless browser)
```bash
apt-get update && apt-get install -y xvfb unzip
```

### 4. Set kredensial (.bot.env sudah termasuk, tapi check)
```bash
cd /root/shopee-farm
cat .bot.env    # BOT_TOKEN, SADCAPTCHA_KEY, OTP_CHANNEL
# kalau bot_key.txt ada → key SadCaptcha terpakai
```

### 5. Restore service bot
```bash
cp /root/shopee-farm/shopee-bot.service /etc/systemd/system/   # (kalau ada)
# atau bikin ulang:
cat > /etc/systemd/system/shopee-bot.service << 'EOF'
[Unit]
Description=Shopee Farm Telegram Bot
After=network-online.target
[Service]
Type=simple
User=root
WorkingDirectory=/root/shopee-farm
EnvironmentFile=/root/shopee-farm/.bot.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/root/sniffenv/bin/python /root/shopee-farm/shopeebot.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now shopee-bot
```

### 6. Restore cron (8 job produksi)
```bash
crontab -e
# tambahkan:
*/30 * * * * cd /root/shopee-farm && /root/sniffenv/bin/python key_watchdog.py --min-alive 2 --min-credits 20 >> /tmp/watchdog.log 2>&1
0 */6 * * * cd /root/shopee-farm && /root/sniffenv/bin/python account_warmer.py --proxy --warm >> /tmp/health.log 2>&1
15 */2 * * * cd /root/shopee-farm && /root/sniffenv/bin/python proxy_health.py >> /tmp/proxyhealth.log 2>&1
*/20 * * * * cd /root/shopee-farm && timeout 300 /root/sniffenv/bin/python prewarm_cache.py 15 --headless >> /tmp/prewarm.log 2>&1
0 2 * * * cd /root/shopee-farm && /root/sniffenv/bin/python farm_production.py --plan 50 >> /tmp/farm_plan.log 2>&1
2 2 * * * cd /root/shopee-farm && /root/sniffenv/bin/python farm_production.py --run >> /tmp/farm_run.log 2>&1
30 */6 * * * cd /root/shopee-farm && /root/sniffenv/bin/python key_manager.py refresh >> /tmp/keyref.log 2>&1
0 6 * * * cd /root/shopee-farm && /root/sniffenv/bin/python captcha_cache.py prune 30 >> /tmp/cacheprune.log 2>&1
```

### 7. Test
```bash
cd /root/shopee-farm
/root/sniffenv/bin/python key_manager.py            # cek key alive
/root/sniffenv/bin/python captcha_cache.py stats    # cek cache
systemctl status shopee-bot                          # cek bot
```

================================================================================
## 🔑 YANG WAJIB DIJAGA (KREDENSIAL)
================================================================================

- `.bot.env`         → BOT_TOKEN + SADCAPTCHA_KEY
- `bot_key.txt`      → SadCaptcha key aktif
- `sadkey_db.json`   → pool key SadCaptcha
- `proxy` lists      → proxies_id_vs.txt, proxies_tiprouter_*.txt
- `accounts.db`      → data akun hasil (SENSITIF)

JANGAN share ke publik. Kalau bocor → rotate semua.

================================================================================
## ARSITEKTUR (ringkas)
================================================================================

```
Nomor → Fingerprint(mobile) → Proxy ID → Signup page
  → CAPTCHA [cache → miss → SadCaptcha API] → OTP WA → inject
  → AKUN: Username/Password/Nomor/UserId/Fingerprint/DeviceID/Cookie
  → notif 🟢/🟡/🔴 → kirim via WA
```

Anti-fraud Shopee: SAP VM (x-sap-sec) fully reversed (VM_100_PERCENT.md).
Signing: page-context fetch (SDK auto-inject). Captcha: cache+API.

Lihat: KESIMPULAN_PROJECT.md, P1_P2_P3_SELESAI.md, SADCAPTCHA_API_BREAKTHROUGH.md
