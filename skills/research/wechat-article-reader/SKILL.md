---
name: wechat-article-reader
description: "Operational guide for reading WeChat articles — cookie management, monitoring, re-verification workflow."
tags: ["wechat", "weixin", "scraper", "article", "browser", "vnc"]
triggers:
  - "read wechat article"
  - "微信公众号文章"
  - "mp.weixin.qq.com"
  - "wechat-reader"
  - "captcha_required"
---

# WeChat Article Reader — Operations Guide

Read WeChat public account articles (`mp.weixin.qq.com`) via `wechat-reader` + persistent Chromium session.

**For initial installation**, see `references/installation.md` in this skill directory.

**For general CDP automation** (non-WeChat tasks like Bilibili login), see `references/vnc-cdp-automation.md`.

## Quick Usage

```bash
cd /opt/wechat-reader && uv run wechat-reader read "<URL>" --json
```

Returns JSON with: `title`, `author`, `content`, `html`, `publish_time`, `account_name`, `status`.
- `status: "ok"` → success, article content in `content` field
- `status: "captcha_required"` → cookies expired, need re-verification (see below)

## Architecture

```
wechat-reader CLI → CDP (port 9222) → Chromium (Xvnc display :99) → mp.weixin.qq.com
User verification → noVNC (port 6080) → Xvnc (:99) → same Chromium
```

Key files:
- Chromium profile (cookies): `/root/.wechat-reader/profiles/default/`
- wechat-reader: `/opt/wechat-reader/` (uv venv)
- noVNC: `/opt/noVNC/`
- One-click start script: `/opt/wechat-reader/start-services.sh`

## Cookie Lifetime

| Cookie | Lifetime | Notes |
|--------|----------|-------|
| `poc_sid` | **30 days** | Main auth cookie, absolute expiry |
| `rewardsn` | Session | Persists while Chrome process runs |
| `wxtokenkey` | Session | Persists while Chrome process runs |

**Effective lifetime:** Up to 30 days, as long as Chrome keeps running. Server reboot or Chrome crash loses session cookies → need re-verification.

Check cookie status:
```bash
cd /opt/wechat-reader && uv run python3 check_cookies.py
```
The `check_cookies.py` script uses raw websocket CDP (see `references/cdp-websocket-fallback.md`). Playwright's `connect_over_cdp` may fail with HTTP 400 — see Pitfalls.

**Important:** Do NOT use bash heredocs (`<< 'PYEOF'`) for multi-line Python scripts containing `&` — bash interprets `&` as backgrounding. Write scripts to a `.py` file first, then execute with `uv run python3 <file>`.

## Re-verification Workflow

When `wechat-reader` returns `captcha_required`:

1. Ensure all services are running:
   ```bash
   bash /opt/wechat-reader/start-services.sh
   ```
2. **Use CDP to navigate Chromium to the target article URL** — this triggers the captcha page automatically:
   ```bash
   cd /opt/wechat-reader && uv run python3 << 'PYEOF'
   from playwright.sync_api import sync_playwright
   with sync_playwright() as p:
       browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
       context = browser.contexts[0]
       pages = context.pages
       page = pages[0] if pages else context.new_page()
       page.goto('<ARTICLE_URL>', timeout=30000)
       print(f"Title: {page.title()}")
       print(f"URL: {page.url}")
   PYEOF
   ```
   **If Playwright fails with 400**, use the raw CDP websocket approach (see `references/cdp-websocket-fallback.md`) to send `Page.navigate` directly:
   ```python
   # After getting ws_url from /json/version, connect and navigate:
   ws_send(sock, {"method": "Target.createTarget", "params": {"url": "<ARTICLE_URL>"}})
   ```
   Or use curl: `curl -s -X PUT "http://localhost:9222/json/new?<ARTICLE_URL>"`
   The page will redirect to `mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?...` — this is the Tencent captcha page.
3. Tell user to open noVNC and drag the slider:
   ```
   http://YOUR_SERVER_IP:6080/vnc_lite.html?autoconnect=true&resize=scale
   ```
   **注意：** nginx配置中noVNC路径是 `/vnc/`，但nginx代理WebSocket不稳定（502、connection reset）。**推荐直接用端口6080访问**。
4. User drags the Tencent captcha slider in noVNC
5. Test: `cd /opt/wechat-reader && uv run wechat-reader read "<ARTICLE_URL>" --json` → should return `ok` with article content

**关键改进：** 不要让用户手动在 noVNC 里输入 URL，用 CDP 直接导航到目标文章 URL。用户只需在 noVNC 里拖拽验证码滑块即可。

**If user says the link doesn't open (502 / ERR_EMPTY_RESPONSE / connection reset):**

1. Check websockify is running: `ps aux | grep websockify | grep -v grep`
2. If not running or stale, restart it:
   ```bash
   kill $(pgrep websockify) 2>/dev/null; sleep 1
   nohup /usr/bin/python3 /usr/bin/websockify --web /opt/noVNC 6080 localhost:5900 &
   ```
3. Reload nginx: `nginx -s reload`
4. Test locally: `curl -s http://127.0.0.1:6080/vnc_lite.html | head -1` (should return HTML)
5. Test via nginx: `curl -s -o /dev/null -w "%{http_code}" http://YOUR_SERVER_IP/vnc/vnc_lite.html` (should return 200)

**nginx WebSocket proxy config must include:**
```nginx
location /vnc/ {
    auth_basic off;
    proxy_pass http://127.0.0.1:6080/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 86400;
    proxy_send_timeout 86400;
}
```

If still failing, check Alibaba Cloud security group — TCP 80 must be open for inbound (noVNC goes through nginx on port 80, not direct 6080).

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Xvnc | 5900 | X display + VNC server (one process) |
| Chromium | 9222 (localhost only) | CDP endpoint for wechat-reader |
| websockify/noVNC | 6080 | Web-based VNC client for user |

Check all running:
```bash
ps aux | grep -E "Xvnc|websockify|chrome.*9222" | grep -v grep | wc -l
# Should be ≥ 3 (at least one process per service)
```

Restart all:
```bash
bash /opt/wechat-reader/start-services.sh
```

## Monitoring Cron Job

A daily cron job (`wechat-reader-cookies-check`) runs at 9:00 AM to:
- Check if Chrome is running (restart if not)
- Check `poc_sid` cookie expiration
- Notify user if ≤7 days remaining or if re-verification needed

## Pitfalls

- **iLink Bot API token ≠ browser cookies** — The Hermes WeChat messaging gateway uses a completely separate auth system. Having a WeChat bot connection does NOT help with reading articles.
| Captcha "Refreshing too often" | Tencent rate limit — wait a few minutes before retrying |
| `send_message` tool fails for WeChat attachments | WeChat adapter has `home_channel` requirement for outbound media; use direct curl to send images instead |
| User gives a URL to read, but noVNC shows "Parameter error" | The Chromium in noVNC needs to navigate to the URL first. Use CDP to control it: `from playwright.sync_api import sync_playwright; browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222'); page = browser.contexts[0].pages[0]; page.goto(URL)`. This triggers the captcha in noVNC for the user to complete. |
- **noVNC access method** — 两种方式：(1) 直接端口 `http://YOUR_SERVER_IP:6080/vnc_lite.html`（推荐，稳定）；(2) nginx代理 `http://YOUR_SERVER_IP/vnc/vnc_lite.html`（可能遇到502/WebSocket问题）。nginx代理不稳定时重启websockify：`kill $(pgrep websockify); sleep 1; nohup /usr/bin/python3 /usr/bin/websockify --web /opt/noVNC 6080 localhost:5900 &`
- **Playwright download fails** → Tsinghua mirror: `UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple`; npm mirror: `PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright`
- **Chrome profile corruption** → On unclean kill, delete lock files: `rm -f /root/.wechat-reader/profiles/default/Default/{Lock,.lock} SingletonLock`
- **`mp.weixin.qq.com/s/test` shows "Parameter error"** — This is NOT a valid article URL. It's a test path that Tencent rejects. Always navigate Chromium to the actual article URL the user wants to read. Using a real URL triggers the captcha; using `s/test` shows a confusing error page in noVNC.
- **Automated captcha solving is NOT feasible** — Tencent drag captcha has anti-automation measures. Manual verification via noVNC is the only reliable approach.
- **`pkill -9` may kill parent shell** — On some setups, `pkill -9 -f chrome` kills the terminal session too. Use specific PIDs: `ps aux | grep chrome | grep -v grep | awk '{print $2}' | xargs kill -9` instead.
- **`send_message` tool can't send WeChat media** — The weixin adapter requires `WEIXIN_HOME_CHANNEL` to be set for outbound media. For screenshots, host on nginx (`/audio/` path, `auth_basic off`) and send the URL instead.
- **Playwright `connect_over_cdp` fails with HTTP 400 or hangs** — Chrome 147+ requires `--remote-allow-origins=*` flag. Without it, Playwright either gets HTTP 400 or hangs indefinitely, and raw websocket gets HTTP 403 (`Rejected an incoming WebSocket connection from the http://127.0.0.1:9222 origin`). **Root cause fix:** Add `--remote-allow-origins=*` to Chrome startup args in `start-services.sh`. **Quick fallback:** Use `websocket-client` package (`uv pip install websocket-client`) — much simpler than raw stdlib websocket. See `references/cdp-websocket-fallback.md`.
- **Python heredocs with `&` break in bash** — Bash interprets `&` inside `<< 'PYEOF'` as backgrounding operators, causing silent failures or `-1` exit codes. Always write Python scripts to a `.py` file and execute with `uv run python3 <file>` instead of using heredocs.
- **Chromium path version-specific** — `/root/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome` may change on playwright update. Check with: `find /root/.cache/ms-playwright -name chrome -type f`
