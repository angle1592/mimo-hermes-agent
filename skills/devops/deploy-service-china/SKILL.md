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

> **Full instructions and pitfalls:** see [`docs/shared/china-infra-patterns.md` — Swap Setup](../../../docs/shared/china-infra-patterns.md#swap-setup-mandatory-for--2gb-ram)

```bash
swapon --show   # If empty → set up swap first (see shared doc)
```

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

If `docker pull` fails even after install, configure a registry mirror. See [`docs/shared/china-infra-patterns.md` — Docker Hub Mirror](../../../docs/shared/china-infra-patterns.md#docker-hub-mirror) for the mirror list and config.

Note: Mirrors may also be unreliable. If Docker pull still fails, download the binary directly (see Step 2).

---

## Step 2: Download Binaries via GitHub Proxy

> **Proxy pattern and verification:** see [`docs/shared/china-infra-patterns.md` — GitHub Proxy](../../../docs/shared/china-infra-patterns.md#github-proxy-for-release-downloads)

```bash
PROXY="https://ghfast.top/"
RELEASE_URL="https://github.com/OWNER/REPO/releases/download/TAG/asset.tar.gz"
curl -L --connect-timeout 15 --max-time 180 -o /tmp/asset.tar.gz "${PROXY}${RELEASE_URL}"
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

Always create a systemd service for persistence. See [`docs/shared/china-infra-patterns.md` — Systemd Service Template](../../../docs/shared/china-infra-patterns.md#systemd-service-template) for the boilerplate.

```bash
systemctl daemon-reload
systemctl enable YOUR-SERVICE
systemctl start YOUR-SERVICE
```

---

## Step 5: MANDATORY Testing

**Never tell the user "it's done" without verifying.** See [`docs/shared/china-infra-patterns.md` — Service Verification Checklist](../../../docs/shared/china-infra-patterns.md#service-verification-checklist) for the standard checks.

Additionally, run a functional test (login, API) specific to the service:

```bash
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

See [`docs/shared/china-infra-patterns.md` — Chrome Profile Corruption Fix](../../../docs/shared/china-infra-patterns.md#chrome-profile-corruption-fix).

### Pitfall: `playwright install-deps` Fails on Alibaba Cloud Linux

See [`docs/shared/china-infra-patterns.md` — Playwright install-deps](../../../docs/shared/china-infra-patterns.md#playwright-install-deps-on-alibaba-cloud-linux).

### Pitfall: Slow pip/Playwright Downloads in China

See [`docs/shared/china-infra-patterns.md` — pip / npm China Mirrors](../../../docs/shared/china-infra-patterns.md#pip--npm-china-mirror-workarounds).

---

### Pitfall: Duplicate CORS Headers Breaks Browser Requests

See [`docs/shared/china-infra-patterns.md` — Duplicate CORS Headers](../../../docs/shared/china-infra-patterns.md#duplicate-cors-headers) for symptoms and fix.

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
| CloakBrowser | pip + GitHub binary | N/A | Stealth Chromium for automation. See `references/cloakbrowser-install.md` |

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
