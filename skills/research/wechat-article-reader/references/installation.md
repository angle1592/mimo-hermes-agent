# Wechat-reader Installation (Alibaba Cloud Linux 4)

Tested 2026-05-03 on Alibaba Cloud Linux 4 (RHEL-like), 2 vCPU, 2GB RAM.

## Step 1: Install wechat-reader

```bash
cd /opt
git clone https://github.com/xiguawang/wechat-reader.git
cd wechat-reader

# Use Tsinghua PyPI mirror — direct PyPI downloads timeout/fail from China
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv sync

# Use npm mirror for Chromium download
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright uv run playwright install chromium
```

**Pitfall:** `uv sync` downloads ~45MB playwright package. Direct PyPI connection resets repeatedly from China servers. Always use Tsinghua mirror.

## Step 2: System dependencies

Playwright's `install-deps` fails on non-Utuntu (uses `apt-get`). Install manually:

```bash
yum install -y nss atk at-spi2-atk cups-libs libdrm mesa-libgbm \
  libXcomposite libXdamage libXrandr alsa-lib pango gtk3 libxkbcommon \
  tigervnc-server xorg-x11-server-Xvfb
pip install websockify
```

## Step 3: noVNC

```bash
git clone https://github.com/novnc/noVNC.git /opt/noVNC --depth 1
```

## Step 4: Start services

```bash
# Xvnc (NOT x11vnc — unavailable on Alibaba Cloud Linux)
Xvnc :99 -geometry 1280x720 -depth 24 -SecurityTypes None -rfbport 5900 -AlwaysShared &

# Chromium on virtual display
DISPLAY=:99 /root/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/root/.wechat-reader/profiles/default" \
  --no-first-run --no-default-browser-check --disable-gpu --no-sandbox \
  --window-size=1280,720 &

# noVNC web proxy
websockify --web /opt/noVNC 6080 localhost:5900 &
```

## Pitfalls encountered

| Problem | Solution |
|---------|----------|
| `x11vnc` not in repos | Use `Xvnc` from `tigervnc-server` instead — creates own X display + VNC in one process |
| `uv sync` connection reset | `UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple` |
| `playwright install chromium` download slow/fails | `PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright` |
| `playwright install-deps` fails with `apt-get: command not found` | Manual `yum install` of listed deps |
| noVNC shows directory listing | websockify needs `--web /opt/noVNC` flag |
| Port 6080 not accessible externally | Alibaba Cloud security group must allow TCP 6080 inbound |
| Captcha "Refreshing too often" | Tencent rate limit — wait a few minutes before retrying |
| `send_message` tool fails for WeChat attachments | WeChat adapter has `home_channel` requirement for outbound media; use direct curl to send images instead |
