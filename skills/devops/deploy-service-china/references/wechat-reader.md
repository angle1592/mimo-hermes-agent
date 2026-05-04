# wechat-reader — Read WeChat Articles Programmatically

GitHub: `xiguawang/wechat-reader`

## What It Does

Reads mp.weixin.qq.com articles via a real browser session. Unlike curl/requests (which hit captcha), it attaches to a running Chrome via CDP and reuses the user's authenticated session.

Returns structured status: `ok`, `captcha_required`, `rate_limited` — not silent garbage.

## Install

```bash
cd /opt
git clone https://github.com/xiguawang/wechat-reader.git
cd wechat-reader
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv sync
# For Playwright browser binaries, use China mirror (default npm registry is slow/fails):
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright uv run playwright install chromium
# Manual deps (apt-get won't work on Alibaba Cloud Linux):
yum install -y nss atk at-spi2-atk cups-libs libdrm mesa-libgbm \
  libXcomposite libXdamage libXrandr alsa-lib pango gtk3 libxkbcommon
```

## Usage

```bash
# Diagnose environment
uv run wechat-reader setup

# Read article (requires Chrome with --remote-debugging-port=9222 already running)
uv run wechat-reader read "https://mp.weixin.qq.com/s/..." --json

# Python API
from wechat_reader import read_article_sync
result = read_article_sync("https://mp.weixin.qq.com/s/...", strategy="auto", timeout=30)
```

## MCP Server

```bash
uv run wechat-reader-mcp
```

Tools: `wechat_read_article`, `wechat_open_article`, `wechat_list_tabs`, `wechat_read_current_tab`, `wechat_get_status`, `wechat_setup`

Note: When status is `captcha_required`, you must set up noVNC (see below), complete verification in the browser, then retry the read command.

## Architecture

wechat-reader does NOT launch its own browser. It attaches to an existing Chrome/Chromium instance via CDP. The user must:
1. Launch Chrome with `--remote-debugging-port=9222`
2. Complete captcha/login manually (e.g., via noVNC, see Step 6)
3. Then wechat-reader can read articles using that authenticated session

## First-Time Verification via noVNC

wechat-reader needs an authenticated Chrome session. On a headless server, set up remote desktop for the user to complete captcha:

```bash
# Start Xvnc (display + VNC in one process — x11vnc is NOT available)
Xvnc :99 -geometry 1280x720 -depth 24 -SecurityTypes None -rfbport 5900 &

# Start noVNC
websockify --web /opt/noVNC 6080 localhost:5900 &

# Launch Chrome on virtual display
DISPLAY=:99 /root/.cache/ms-playwright/chromium-*/chrome-linux64/chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/root/.wechat-reader/profiles/default" \
  --no-first-run --no-default-browser-check \
  --disable-gpu --no-sandbox --window-size=1280,720 \
  "https://mp.weixin.qq.com/s/ARTICLE_URL"
```

User opens `http://PUBLIC-IP:6080/vnc_lite.html?autoconnect=true&resize=scale`, drags the captcha, then wechat-reader can read articles.

**Port 6080 security group:** Usually blocked by default. User must open TCP 6080 in Alibaba Cloud security group. Can close after verification (cookies persist in Chromium profile). Direct port access (`:6080`) is simpler than nginx proxy since noVNC uses WebSocket.

**nginx proxy alternative:** If port can't be opened, add `location /vnc/` with `auth_basic off` and WebSocket upgrade headers to the nginx server block. But direct port is preferred.

```bash
# After verification, read articles:
cd /opt/wechat-reader
uv run wechat-reader read "https://mp.weixin.qq.com/s/..." --json
```

**For ongoing operations** (cookie monitoring, re-verification, cron job), see `wechat-article-reader` skill.

## Tencent Captcha Details

The WeChat captcha is a **Tencent drag-captcha** (tc-* CSS classes). Key DOM elements:
- `a.weui-btn_primary` — "去验证" button (must click first to reveal captcha)
- `#tcaptcha_wrapper_transform_dy` — captcha container (initially off-screen at y=-1000000)
- `.tcaptcha-transform` — main captcha popup (362×362 overlay)
- `.tc-embed-verify-btn` — verify button inside iframe
- `.t-captcha-popup-mask` — background mask overlay
- `.ticons ticon-refresh` — refresh captcha button
- `iframe[src*="captcha.gtimg.com"]` — captcha content iframe

**Flow:** Page loads "环境异常" → user clicks "去验证" → captcha popup appears → drag verification → page redirects to article.

**Rate limiting:** Too many attempts shows "Refreshing too often". Refresh button resets the captcha but doesn't bypass rate limiting. Wait before retrying.

**Automated solving is NOT feasible.** The Tencent captcha uses anti-automation measures (iframe sandboxing, pointer event tracking, timing analysis). Even with Playwright controlling the browser programmatically, drag-captcha solving is unreliable. Manual verification via noVNC is the only reliable approach.

## Practical Advice

For one-off article reading, **copy-paste is faster** than setting up the full wechat-reader + noVNC pipeline. The tool is designed for automated workflows that process many articles.

## Known Issues

- WeChat iLink Bot API token (used by Hermes Weixin gateway) is NOT the same as browser cookies — they're completely separate auth systems. Having a WeChat bot connection does NOT help with reading articles.
- Headless Chrome still hits captcha. A real browser session (even on Xvnc virtual display) with manual verification is required.
- On Alibaba Cloud Linux 4, Playwright reports "OS not officially supported" and downloads Ubuntu fallback build. Works fine.
- Chrome `--user-data-dir` can corrupt on unclean kill. Delete `SingletonLock` and `Lock` files, or use fresh dir.
- `pkill -9 chrome` is particularly bad — prefer `pkill chrome` (SIGTERM) to allow clean shutdown. If corrupted, `rm -f ~/.wechat-reader/profiles/Default/{Lock,.lock} SingletonLock`.
