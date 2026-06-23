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
      - references/repo-sync.md
      - references/fastapi-mariadb.md
      - references/cloakbrowser-install.md
      - references/ssh-reverse-tunnel-proxy.md
      - references/bis-neer-api.md
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

### Pitfall: Docker Hub Mirror (Unreliable in China)

Docker Hub mirrors (`mirror.ccs.tencentyun.com`, `registry.docker-cn.com`, etc.) are **unreliable** — they frequently go down or become unreachable. If `docker pull` fails with mirror errors, the best solution is to route Docker through a local proxy (mihomo/Clash).

**Preferred: Use local proxy (mihomo/Clash)**

If a local proxy is running (e.g., mihomo on port 7890), configure Docker to use it:

```bash
# 1. Configure Docker daemon proxy via systemd override
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/proxy.conf << 'EOF'
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
Environment="NO_PROXY=localhost,127.0.0.1,172.16.0.0/12,10.0.0.0/8,192.168.0.0/16"
EOF

# 2. Remove broken mirrors (optional but cleaner)
cat > /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": []
}
EOF

# 3. Restart Docker
systemctl daemon-reload && systemctl restart docker
```

**Fallback: Configure mirrors**

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

## Step 3: Port Strategy & Nginx Reverse Proxy

Alibaba Cloud security groups block non-standard ports by default. Two strategies:

### Strategy A: Subpath on Port 80 (default, zero security-group changes)

Best for: web UIs, services with static assets, when you don't want to bother the user.

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

### Strategy B: Dedicated Port (cleaner for APIs)

Best for: REST APIs, backend services without static assets, when cleaner separation is preferred.

```bash
# 1. Check which ports are already open from public IP
curl -s --connect-timeout 3 -o /dev/null -w "%{http_code}" http://PUBLIC-IP:80/    # usually open
curl -s --connect-timeout 3 -o /dev/null -w "%{http_code}" http://PUBLIC-IP:6080/  # if noVNC

# 2. Ask user to open the desired port in Alibaba Cloud console
#    (ECS → Security Groups → Inbound Rules → Add: TCP/PORT/0.0.0.0/0)

# 3. After user opens port, verify:
curl -s --connect-timeout 3 -o /dev/null -w "%{http_code}" http://PUBLIC-IP:NEW-PORT/
# Expect: 200 (or non-timeout). If exit code 28 (timeout), still blocked.

# 4. Nginx config for dedicated port (separate server block):
```

```nginx
server {
    listen NEW_PORT;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:BACKEND_PORT/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Decision tree:**
- User can/will open port in security group? → Strategy B (dedicated port)
- User doesn't want to touch security group? → Strategy A (subpath on 80)
- Service has static assets that break with subpath? → Strategy B (or fix base URL)

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

# 1. Set VNC password (NEVER use -SecurityTypes None on public servers!)
mkdir -p /root/.vnc
VNC_PASS=$(openssl rand -base64 12 | head -c 12)
echo -e "${VNC_PASS}\n${VNC_PASS}\nn" | vncpasswd /root/.vnc/passwd
chmod 600 /root/.vnc/passwd
echo "Save this password: $VNC_PASS"

# 2. Start Xvnc WITH password authentication
Xvnc :99 -geometry 1280x720 -depth 24 \
  -SecurityTypes VncAuth -rfbauth /root/.vnc/passwd \
  -rfbport 5900 -AlwaysShared &

# 3. Start noVNC (WebSocket-to-VNC bridge)
websockify --web /opt/noVNC 6080 localhost:5900 &

# 4. Launch browser on virtual display
DISPLAY=:99 chromium --remote-debugging-port=9222 \
  --user-data-dir="/root/.browser-profiles/default" \
  --no-first-run --no-default-browser-check \
  --disable-gpu --no-sandbox --window-size=1280,720 "https://target-url"

# 5. Proxy through nginx (port 6080 usually blocked by security group)
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

### Pitfall: Duplicate CORS Headers Breaks Browser Requests

If the backend framework (FastAPI, Express, etc.) already has its own CORS middleware (e.g., FastAPI's `CORSMiddleware`), do **NOT** also add CORS headers in nginx. Browsers reject responses with duplicate `Access-Control-Allow-Origin` headers, causing `TypeError: Failed to fetch` even though curl/Python scripts work fine (they don't enforce CORS).

**Symptoms:**
- `curl -i` shows `Access-Control-Allow-Origin: *` appearing twice
- Browser console: `TypeError: Failed to fetch`
- curl / Python test scripts work normally

**Fix:** Remove all `add_header Access-Control-Allow-*` and `if ($request_method = OPTIONS)` blocks from nginx. Let the backend's CORS middleware handle it exclusively.

```nginx
# WRONG — nginx + backend both add CORS headers → duplicate
location / {
    proxy_pass http://127.0.0.1:8000/;
    add_header Access-Control-Allow-Origin * always;       # ← REMOVE
    add_header Access-Control-Allow-Methods "..." always;  # ← REMOVE
    if ($request_method = OPTIONS) { return 204; }         # ← REMOVE
}

# RIGHT — only nginx proxy, backend handles CORS
location / {
    proxy_pass http://127.0.0.1:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Verification:**
```bash
# Should show Access-Control-Allow-Origin exactly ONCE
curl -s -D - -H "Origin: http://example.com" http://PUBLIC-IP:PORT/api/endpoint -o /dev/null \
  | grep -i "access-control-allow-origin"
```

## Common Pitfalls

1. **Using `get.docker.com` install script** — Blocked in China. Use Alibaba Cloud mirror repo.
2. **Docker CE repo `$releasever` mismatch** — Alibaba Cloud Linux 4 != CentOS 4. Hardcode to `9`.
3. **Assuming Docker Hub pull works** — Often fails. Prefer direct binary download.
4. **Direct GitHub download** — Too slow. Use `ghfast.top` or similar proxy.
5. **Opening ports in security group** — Can't be done from the server CLI, but the user can open ports via the Alibaba Cloud console. Two strategies (see Step 3 for decision framework):
   - **Subpath on port 80** (default, zero-config): proxy via nginx, no security group change needed. Watch for base URL mismatches.
   - **Dedicated port** (cleaner for APIs): user opens the port in security group console. Better separation, no path prefix issues. Verify with `curl -s --connect-timeout 3 -o /dev/null -w "%{http_code}" http://PUBLIC-IP:PORT/` from the server — timeout (exit code 28) = blocked by security group.
6. **Telling user it works without testing** — Always curl localhost first, then curl public IP.
7. **Weak default passwords** — Some tools require 12+ char passwords (e.g., FileBrowser v2.63+).
8. **Duplicate CORS headers** — If backend has CORS middleware (FastAPI CORSMiddleware, Express cors()), do NOT also add CORS headers in nginx. Browsers reject duplicate `Access-Control-Allow-Origin` → `TypeError: Failed to fetch`. curl works fine because it doesn't enforce CORS. Remove nginx CORS, let backend handle it.
9. **`docker compose up -d` blocks in terminal tool** — The terminal tool detects it as a long-lived process and blocks. Use `terminal(background=true, notify_on_complete=true)`, then `process(action='wait')`. Do NOT use `nohup`/`disown` wrappers — the terminal tool rejects those.
10. **Adding nginx location to existing server block** — When the server already has a `server_name <IP>` block (e.g., hermes-dashboard.conf), add new `location` blocks to it instead of creating a separate `server_name _` block. Multiple `server_name _` blocks cause "conflicting server name" warnings and the first one wins, so requests to other blocks go to the default nginx server (404). Also check if the server block has `auth_basic` — new locations inherit it. Add `auth_basic off;` to each public location, otherwise users get a 401 login popup.
11. **Docker port binding `127.0.0.1` vs `0.0.0.0`** — `ports: "127.0.0.1:8090:8080"` binds ONLY to localhost → `ERR_CONNECTION_REFUSED` from external clients. For services that need external access (via security group port), use `"0.0.0.0:8090:8080"` or just `"8090:8080"`. Use `127.0.0.1` only when the service should be nginx-proxied only (never direct-accessed). After changing, must `docker compose down && docker compose up -d` (not just restart) for port binding to take effect.
12. **External API domains may redirect** — APIs behind Cloudflare frequently change domains (e.g., `api.frankfurter.app` → `api.frankfurter.dev` with `/v1/` prefix). Before writing nginx proxy_pass, always test with `curl -sIL` to check for 301 redirects and follow the chain to the final URL. Use that final domain in proxy_pass.
14. **Static site + API proxy pattern** — For frontend-only sites calling external APIs, use nginx `alias` for static files + separate `proxy_pass` for API. See `references/static-site-api-proxy.md` for the full pattern.
15. **PM2 for Node.js services** — For Node.js apps (SillyTavern, Uptime Kuma, etc.), use PM2 instead of raw systemd: `npx pm2 start app.js --name NAME && npx pm2 save && npx pm2 startup`. First boot may be slow (frontend compilation) — wait 20s before checking port. **SillyTavern specific:** MUST enable `basicAuthMode: true` when `listen: true` — disabling whitelist without enabling auth causes crash loop. See `references/sillytavern-pm2.md`.
17. **noVNC without authentication = open backdoor** — `-SecurityTypes None` means anyone who discovers the port (6080 or 5900) gets full desktop access with zero authentication. Internet scanners constantly probe these ports. **Always use `-SecurityTypes VncAuth -rfbauth /root/.vnc/passwd`** and set a password with `vncpasswd` before starting Xvnc. If noVNC is only needed temporarily (e.g., QR scan login), kill both Xvnc and websockify immediately after use. Leaving them running overnight is how intrusions happen.
18. **Memory-optimized Docker Compose for 2GB servers** — For multi-container stacks (PostgreSQL + Redis + app), add `deploy.resources.limits.memory` to each service to prevent OOM. Typical budget for 2GB: Postgres 300MB, Redis 128MB, app 512MB. Pass PostgreSQL tuning via `command:` override (`shared_buffers=64MB`, `effective_cache_size=128MB`, `max_connections=100`). For Redis: `--maxmemory 80mb --maxmemory-policy allkeys-lru`. Set `shm_size: 64mb` for PostgreSQL.

---

## Quick Reference: Common Services

| Service | Binary Source | Default Port | Notes |
|---------|--------------|-------------|-------|
| FastAPI + MariaDB | pip + system MariaDB | 8000 | See `references/fastapi-mariadb.md` for full pattern incl. OneNET auth pitfalls |
| FileBrowser | GitHub release | 8080 | Go binary, ~30MB, very lightweight. See `references/filebrowser.md` |
| Alist | GitHub release | 5244 | Can mount cloud storage |
| Uptime Kuma | Docker | 3001 | Node.js, needs more RAM |
| Gitea | GitHub release | 3000 | Self-hosted Git |
| wechat-reader | GitHub clone | 9222 (CDP) | WeChat article reader. See `references/wechat-reader.md` |
| Sub2API | Docker Compose | 8090 | AI API gateway (Claude/OpenAI/Gemini). Memory-optimized for 2GB. See `references/sub2api-deployment.md` + `references/sub2api-api.md` |
| Static Site + API Proxy | nginx alias + proxy_pass | 80 (subpath) | Frontend-only sites calling external APIs. See `references/static-site-api-proxy.md` |
| BIS NEER Data | SDMX REST API (CSV) | N/A | Effective exchange rate indices. nginx proxy + CSV parser. See `references/bis-neer-api.md` |
| CloakBrowser | pip + GitHub binary | N/A | Stealth Chromium for automation. See `references/cloakbrowser-install.md` |
| SillyTavern | GitHub clone + npm | 8002 | LLM chat frontend (Node.js). Use PM2 for process management. See `references/sillytavern-pm2.md` |

For 2C2G machines, prefer Go binaries over Docker/Node.js services.

## Accessing Blocked Sites (GFW Bypass)

Server in China can't reach many foreign sites. If the user has a phone with working proxy/VPN, use an SSH reverse tunnel to forward the phone's proxy port to the server. See `references/ssh-reverse-tunnel-proxy.md` for the full pattern.

---

## Post-Incident Diagnostics

If the server became unresponsive or was hard-rebooted, see `references/server-diagnostics.md` for the investigation workflow (journal forensics, OOM detection, crash cause triage).

## Test Data Generation

Generate realistic posture monitoring data with `scripts/seed-posture-data.py`:

```bash
# 7-day reminder-aware data (default, best for demos with alert features)
python3 scripts/seed-posture-data.py --days 7 --sql-file /tmp/seed.sql
mysql -u root < /tmp/seed.sql

# 3-week data with ratio mode (continuous abnormal posture)
python3 scripts/seed-posture-data.py --days 21 --mode ratio --sql-file /tmp/seed.sql

# Custom range
python3 scripts/seed-posture-data.py --days 14 --start-date 2026-05-01 --sql-file /tmp/seed.sql
```

Two modes:
- **`--mode reminder`** (default): Episode-based. Abnormal posture happens in short bursts (30-60s each), simulating a system with posture alerts. Realistic: ~15-45 reminders/day in week 1, dropping to ~5-15 in week 3. Best for defense demos with reminder functionality.
- **`--mode ratio`**: Continuous ratio-based. Each record randomly picks posture type based on weekly ratios. Produces more abnormal records (~1000+/day). Better for showing dramatic score differences (55→85).

Both modes simulate a student's daily schedule with weekday/weekend differences and fatigue-based degradation.
- **Week 1 (初始)**: score ~55-65, daily abnormal ~2.5h — poor posture habits
- **Week 2 (改善)**: score ~65-75, daily abnormal ~1.5h — gradual improvement
- **Week 3 (习惯养成)**: score ~75-85, daily abnormal ~50min — good habits formed
- **Weekday vs weekend**: different wake times, posture distributions, outdoor periods
- **Fatigue model**: hunchback probability increases with awake hours
- Each day produces meaningfully different data (not copy-paste)

## Filesystem Cleanup

When the home directory accumulates test files, scraped HTML, old scripts, and cache, see `references/filesystem-cleanup.md` for the audit procedure and safe-to-delete checklist.

## Automated Repo Sync

Keep a GitHub repo in sync with local Hermes config and custom skills. Includes mandatory two-pass sanitization (field-level + regex catch-all) to prevent privacy leaks. See `references/repo-sync.md` for the full pattern (whitelist, sanitization, cron setup, mirror credentials).
