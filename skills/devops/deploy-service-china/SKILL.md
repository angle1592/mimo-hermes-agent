---
name: deploy-service-china
description: Deploy self-hosted services on Alibaba Cloud Linux in China. Covers Docker CE installation, GitHub binary downloads via proxy, nginx reverse proxy for security groups, and mandatory testing flow.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [devops, china, docker, nginx, alibaba-cloud, deployment]
    related_skills: [china-github-mirror, hermes-agent]
    related_files:
      - references/sensenova-provider.md
---

# Deploy Services in China (Alibaba Cloud Linux)

Repeatable pattern for deploying self-hosted services on Alibaba Cloud servers in mainland China. Covers the common pitfalls: blocked Docker Hub, slow GitHub downloads, security group port restrictions.

## When to Use

- Installing any service via Docker or binary on Alibaba Cloud
- User asks to set up a file server, monitoring panel, database UI, etc.
- Service needs to be accessible from the internet

## Environment

- Alibaba Cloud Linux 4 (based on Anolis OS / RHEL 9)
- Typical specs: 2 vCPU / 2GB RAM
- Nginx on port 80 (usually open in security group)
- Other ports may be blocked by security group

---

### Pitfall: Hermes Auto-Update Crashes Low-Memory Servers

Hermes auto-update can pull 100+ commits and reinstall pip/npm dependencies. On 2GB machines without swap, this overwhelms RAM + disk I/O simultaneously, causing a silent kernel hang (no OOM, no logs, SSH unresponsive). The user will have to hard reboot.

**Prevention:**
- Always ensure swap is active before updates (see Step 0)
- Check update scope: `cat ~/.hermes/logs/update.log | tail -20` — if "Found N new commit(s)" with N > 50, be cautious
- Schedule large updates during monitored hours, not overnight

## Step 0: Swap Setup (MANDATORY for ≤2GB RAM)

2GB RAM with no swap will crash during heavy I/O operations (dependency installs, Hermes updates, large git pulls). The system becomes unresponsive — SSH hangs, disk I/O maxes out, requires hard reboot.

```bash
# Create 2GB swap file
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Persist across reboots
echo '/swapfile swap swap defaults 0 0' >> /etc/fstab

# Low swappiness — only use swap as emergency buffer
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swap.conf
sysctl -p /etc/sysctl.d/99-swap.conf

# Verify
swapon --show
free -h
```

### Pitfall: No Swap = Silent Crash

Hermes updates pull many commits and reinstall pip/npm dependencies. With 2GB RAM and no swap, concurrent package downloads + extraction can exhaust memory, causing the kernel to hang (no OOM kill, just freeze). Always set up swap before running heavy update operations.

---

## Step 1: Docker CE Installation

Docker Hub and `get.docker.com` are often blocked in China. Use the Alibaba Cloud mirror repo.

```bash
# Add Alibaba Cloud Docker CE repo
yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo

# CRITICAL: Alibaba Cloud Linux 4 reports as version 4, but Docker CE repo
# needs CentOS/RHEL 9. Fix the repo:
sed -i 's|\$releasever|9|g' /etc/yum.repos.d/docker-ce.repo

# Install
yum install -y docker-ce docker-ce-cli containerd.io

# Enable and start
systemctl enable docker && systemctl start docker
```

### Pitfall: Docker Hub Mirror

If `docker pull` fails even after install, configure a registry mirror:

```bash
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://registry.docker-cn.com",
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
EOF
systemctl daemon-reload && systemctl restart docker
```

Note: Mirrors may also be unreliable. If Docker pull still fails, download the binary directly (see Step 2).

---

## Step 2: Download Binaries via GitHub Proxy

Direct GitHub downloads are slow or timeout from China. Use a GitHub proxy mirror.

```bash
# Pattern: prepend proxy URL to the GitHub raw/release URL
# Working proxies (test before use, they change):
#   https://ghfast.top/
#   https://ghproxy.com/
#   https://mirror.ghproxy.com/

# Example: download a release asset
PROXY="https://ghfast.top/"
RELEASE_URL="https://github.com/OWNER/REPO/releases/download/TAG/asset.tar.gz"
curl -L --connect-timeout 15 --max-time 180 -o /tmp/asset.tar.gz "${PROXY}${RELEASE_URL}"
```

### Pitfall: Incomplete Downloads

Always verify download integrity:

```bash
# Check file size matches expected
ls -la /tmp/asset.tar.gz
# Try to extract / run
tar xzf /tmp/asset.tar.gz 2>&1 || echo "CORRUPTED - retry download"
# For binaries, test immediately
./binary --version
```

If download is corrupted (Bus error, unexpected EOF), retry with a different proxy.

---

## Step 3: Nginx Reverse Proxy

Alibaba Cloud security groups often block non-standard ports (8080, 3000, etc.). The safest approach: proxy through nginx on port 80.

```nginx
# Add to existing server block or create new one
location /your-service/ {
    auth_basic off;                    # if server has auth_basic, disable for this location
    proxy_pass http://127.0.0.1:PORT/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 500m;         # for file upload services
}
```

```bash
# Always validate before reload
nginx -t && nginx -s reload
```

### Pitfall: Subpath Proxy (Base URL Mismatch)

When proxying a service at a subpath (e.g., `/files/`), the backend service doesn't know about this prefix. All its static assets (JS, CSS, images) are requested from `/static/...` instead of `/files/static/...`, causing the page to load as blank white.

**Fix:** Configure the service's base URL to match the nginx location path:

```bash
# FileBrowser example
# In config or CLI flag:
filebrowser --baseurl /files

# Grafana example
# grafana.ini: [server] root_url = %(protocol)s://%(domain)s:%(http_port)s/grafana/
```

**Verification:** After configuring, check that HTML references the correct paths:
```bash
curl -s http://localhost:PORT/ | grep -o 'src="[^"]*"'
# Should show: src="/files/static/..."  (not src="/static/...")
```

If the service has no base URL option, an alternative is to proxy at root (`location /`) on a dedicated port, but this requires opening that port in the security group.

### Pitfall: Trailing Slash

`proxy_pass http://127.0.0.1:8080/;` (with trailing slash) strips the location prefix.
`location /files/` + `proxy_pass http://127.0.0.1:8080/;` → `/files/foo` becomes `/foo` on backend.

Match the backend's expected base URL.

---

## Step 4: Systemd Service

Always create a systemd service for persistence:

```bash
cat > /etc/systemd/system/YOUR-SERVICE.service << 'EOF'
[Unit]
Description=Your Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/your-service --config /etc/your-service/config.json
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable YOUR-SERVICE
systemctl start YOUR-SERVICE
```

---

## Step 5: MANDATORY Testing

**Never tell the user "it's done" without verifying.**

```bash
# 1. Service is running
systemctl status YOUR-SERVICE --no-pager | head -10

# 2. Port is listening
ss -tlnp | grep YOUR-PORT

# 3. Local HTTP test
curl -s -o /dev/null -w "%{http_code}" http://localhost:YOUR-PORT/
# Expect: 200

# 4. Public access test (through nginx)
curl -s -o /dev/null -w "%{http_code}" http://PUBLIC-IP/your-path/
# Expect: 200 (or 401 if auth required — that's OK)

# 5. Functional test (login, API, etc.)
curl -s -X POST http://localhost:YOUR-PORT/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

Only report success after ALL tests pass.

---

## Step 6: Remote Browser via noVNC (for Captcha/Login Verification)

When a service requires human browser interaction (captcha, OAuth login, QR scan) on a headless server, set up a virtual desktop with VNC access.

**Use cases:** WeChat article scraping (wechat-reader), any site with anti-bot captcha, OAuth flows requiring browser interaction.

**Key insight:** Use **Xvnc** (from `tigervnc-server`) which provides both the X display AND VNC server in a single process. Do NOT use Xvfb + x11vnc — `x11vnc` is not available on Alibaba Cloud Linux 4 (`yum install x11vnc` fails).

```bash
# Install VNC + noVNC
yum install -y tigervnc-server    # provides Xvnc (display + VNC in one)
pip install websockify
git clone https://github.com/novnc/noVNC.git /opt/noVNC --depth 1

# 1. Start Xvnc (X display + VNC server, one process)
Xvnc :99 -geometry 1280x720 -depth 24 \
  -SecurityTypes None -rfbport 5900 -AlwaysShared \
  -AcceptKeyEvents -AcceptPointerEvents &

# 2. Start noVNC (WebSocket-to-VNC bridge)
websockify --web /opt/noVNC 6080 localhost:5900 &

# 3. Launch browser on virtual display
DISPLAY=:99 chromium --remote-debugging-port=9222 \
  --user-data-dir="/root/.browser-profiles/default" \
  --no-first-run --no-default-browser-check \
  --disable-gpu --no-sandbox --window-size=1280,720 "https://target-url"

# 4. Proxy through nginx (port 6080 usually blocked by security group)
# Add to nginx server block (before closing }):
#     location /vnc/ {
#         auth_basic off;
#         proxy_pass http://127.0.0.1:6080/;       # trailing slash strips prefix
#         proxy_http_version 1.1;
#         proxy_set_header Upgrade $http_upgrade;   # REQUIRED for WebSocket
#         proxy_set_header Connection "upgrade";
#         proxy_set_header Host $host;
#         proxy_read_timeout 86400;
#     }
# Then: nginx -t && nginx -s reload
```

User accesses: `http://PUBLIC-IP/vnc/vnc_lite.html?autoconnect=true&resize=scale`

**User-facing URL:** Always use `vnc_lite.html` (not `vnc.html`) — it auto-connects without showing a connection dialog. Add `autoconnect=true&resize=scale` for instant connection with auto-scaling.

After verification, the browser cookies persist in `--user-data-dir`. Tools like `wechat-reader` can then attach via CDP (`--remote-debugging-port=9222`) to reuse the authenticated session.

### Pitfall: `x11vnc` Not Available

`x11vnc` is NOT in Alibaba Cloud Linux repos. `yum install x11vnc` → "No match for argument". Always use `Xvnc` from `tigervnc-server` instead. If Xvfb was started separately, kill it first — Xvnc creates its own display.

### Pitfall: Chrome Profile Corruption on Unclean Shutdown

If Chrome is killed (e.g., `pkill -9 chrome`) without clean shutdown, the `--user-data-dir` profile can corrupt. Symptoms: Chrome starts but shows blank page or crashes immediately.

**Fix:** Delete the lock files:
```bash
rm -f /root/.browser-profiles/default/Default/{Lock,.lock}
rm -f /root/.browser-profiles/SingletonLock
```
Or use a fresh profile dir for each session.

### Pitfall: `playwright install-deps` Fails on Alibaba Cloud Linux

Playwright's `install-deps` uses `apt-get` (Ubuntu-only). On Alibaba Cloud Linux (yum-based), install manually:

```bash
yum install -y nss atk at-spi2-atk cups-libs libdrm mesa-libgbm \
  libXcomposite libXdamage libXrandr alsa-lib pango gtk3 libxkbcommon
```

### Pitfall: Slow pip/Playwright Downloads in China

Use Tsinghua mirror for Python packages:
```bash
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv sync
pip install PACKAGE -i https://pypi.tuna.tsinghua.edu.cn/simple
```

For Playwright browser binaries, use npmmirror:
```bash
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright playwright install chromium
```

Without mirrors, downloads frequently timeout or get connection-reset.

---

## Common Pitfalls

1. **Using `get.docker.com` install script** — Blocked in China. Use Alibaba Cloud mirror repo.
2. **Docker CE repo `$releasever` mismatch** — Alibaba Cloud Linux 4 != CentOS 4. Hardcode to `9`.
3. **Assuming Docker Hub pull works** — Often fails. Prefer direct binary download.
4. **Direct GitHub download** — Too slow. Use `ghfast.top` or similar proxy.
5. **Opening ports in security group** — You can't do this from the server. Use nginx reverse proxy on port 80 instead.
6. **Telling user it works without testing** — Always curl localhost first, then curl public IP.
7. **Weak default passwords** — Some tools require 12+ char passwords (e.g., FileBrowser v2.63+).

---

## Quick Reference: Common Services

| Service | Binary Source | Default Port | Notes |
|---------|--------------|-------------|-------|
| FileBrowser | GitHub release | 8080 | Go binary, ~30MB, very lightweight. See `references/filebrowser.md` |
| Alist | GitHub release | 5244 | Can mount cloud storage |
| Uptime Kuma | Docker | 3001 | Node.js, needs more RAM |
| Gitea | GitHub release | 3000 | Self-hosted Git |
| wechat-reader | GitHub clone | 9222 (CDP) | WeChat article reader. See `references/wechat-reader.md` |

For 2C2G machines, prefer Go binaries over Docker/Node.js services.

---

## Post-Incident Diagnostics

If the server became unresponsive or was hard-rebooted, see `references/server-diagnostics.md` for the investigation workflow (journal forensics, OOM detection, crash cause triage).

## Filesystem Cleanup

When the home directory accumulates test files, scraped HTML, old scripts, and cache, see `references/filesystem-cleanup.md` for the audit procedure and safe-to-delete checklist.
