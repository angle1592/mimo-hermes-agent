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
cd /opt/wechat-reader && uv run python3 << 'PYEOF'
from playwright.sync_api import sync_playwright
from datetime import datetime
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    for c in browser.contexts[0].cookies():
        if c['name'] == 'poc_sid':
            exp = c.get('expires', -1)
            if exp > 0:
                days = (exp - datetime.now().timestamp()) / 86400
                print(f"poc_sid expires in {days:.1f} days ({datetime.fromtimestamp(exp)})")
            else:
                print("poc_sid: session cookie")
            break
    browser.close()
PYEOF
```

## Re-verification Workflow

When `wechat-reader` returns `captcha_required`:

1. Ensure all services are running:
   ```bash
   bash /opt/wechat-reader/start-services.sh
   ```
2. Tell user to open noVNC link and complete captcha:
   ```
   http://<server-ip>:6080/vnc_lite.html?autoconnect=true&resize=scale
   ```
3. User drags the Tencent captcha slider
4. Test: `cd /opt/wechat-reader && uv run wechat-reader read "https://mp.weixin.qq.com/s/test" --json` → should return `ok` or article content

**If user says the link doesn't open:** Check Alibaba Cloud security group — TCP 6080 must be open for inbound. Can close it again after verification for security (VNC is unencrypted, no password).

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
- **"Refreshing too often"** — Tencent captcha rate limit. Wait a few minutes before retrying.
- **nginx auth_basic blocks noVNC** — The Hermes Dashboard nginx config has auth_basic on the root server block. Either use direct port 6080 access, or add a `location /vnc/` block with `auth_basic off`.
- **Playwright download fails** → Tsinghua mirror: `UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple`; npm mirror: `PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright`
- **Chrome profile corruption** → On unclean kill, delete lock files: `rm -f /root/.wechat-reader/profiles/default/Default/{Lock,.lock} SingletonLock`
- **Automated captcha solving is NOT feasible** — Tencent drag captcha has anti-automation measures. Manual verification via noVNC is the only reliable approach.
- **`pkill -9` may kill parent shell** — On some setups, `pkill -9 -f chrome` kills the terminal session too. Use specific PIDs: `ps aux | grep chrome | grep -v grep | awk '{print $2}' | xargs kill -9` instead.
- **`send_message` tool can't send WeChat media** — The weixin adapter requires `WEIXIN_HOME_CHANNEL` to be set for outbound media. For screenshots, host on nginx (`/audio/` path, `auth_basic off`) and send the URL instead.
- **Chromium path version-specific** — `/root/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome` may change on playwright update. Check with: `find /root/.cache/ms-playwright -name chrome -type f`
