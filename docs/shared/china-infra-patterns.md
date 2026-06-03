# China Infrastructure Patterns (Shared Reference)

Common patterns for deploying and maintaining services on China-based servers (Alibaba Cloud, etc.). Referenced by multiple skills to avoid duplication.

---

## Swap Setup (Mandatory for <= 2GB RAM)

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

Real case: 2C2G server running Hermes auto-update (100+ commits), pip/npm simultaneously downloading and extracting dependencies — memory and disk I/O both maxed out, system completely unresponsive. No OOM logs — the kernel couldn't even run OOM killer. Only fix was hard reboot.

**Always verify swap exists before heavy operations:**
```bash
swapon --show
# If empty → set up swap first
```

---

## Docker Hub Mirror

`docker pull` from `registry-1.docker.io` frequently fails in China. Configure mirrors in `/etc/docker/daemon.json`:

```json
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://registry.docker-cn.com",
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
```

```bash
sudo systemctl daemon-reload && sudo systemctl restart docker
```

Note: These mirrors come and go. If `docker pull` still fails after configuring, consider downloading binaries directly via a GitHub proxy instead.

---

## GitHub Proxy for Release Downloads

Direct GitHub downloads are slow or timeout from China. Prepend a proxy URL:

```bash
# Working proxies (test before use, they change):
#   https://ghfast.top/
#   https://ghproxy.com/
#   https://mirror.ghproxy.com/

PROXY="https://ghfast.top/"
RELEASE_URL="https://github.com/OWNER/REPO/releases/download/TAG/asset.tar.gz"
curl -L --connect-timeout 15 --max-time 180 -o /tmp/asset.tar.gz "${PROXY}${RELEASE_URL}"
```

Always verify download integrity:
```bash
ls -la /tmp/asset.tar.gz
tar xzf /tmp/asset.tar.gz 2>&1 || echo "CORRUPTED - retry with different proxy"
```

---

## Nginx Reverse Proxy Template

### Subpath on Port 80 (zero security-group changes)

```nginx
location /your-service/ {
    auth_basic off;                    # if parent server has auth_basic
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
nginx -t && nginx -s reload
```

### Pitfall: Subpath Base URL Mismatch

The backend doesn't know about the nginx prefix. Static assets request `/static/...` instead of `/your-service/static/...`, showing a blank page.

**Fix:** Set the service's base URL to match the nginx location (e.g. `filebrowser --baseurl /files`, Grafana `root_url`).

### Pitfall: Trailing Slash

`proxy_pass http://127.0.0.1:8080/;` (with trailing slash) strips the location prefix.
`location /files/` + `proxy_pass ...8080/;` => `/files/foo` becomes `/foo` on backend.

---

## Systemd Service Template

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

## pip / npm China Mirror Workarounds

```bash
# Python packages — Tsinghua mirror
pip install PACKAGE -i https://pypi.tuna.tsinghua.edu.cn/simple
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv sync

# Playwright browser binaries — npmmirror
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright playwright install chromium
```

Without mirrors, downloads frequently timeout or get connection-reset.

---

## Chrome Profile Corruption Fix

If Chrome is killed without clean shutdown (`pkill -9 chrome`), the profile can corrupt. Symptoms: blank page or immediate crash.

```bash
rm -f /root/.browser-profiles/default/Default/{Lock,.lock}
rm -f /root/.browser-profiles/SingletonLock
# Or for wechat-reader:
rm -f /root/.wechat-reader/profiles/default/Default/{Lock,.lock} SingletonLock
```

---

## Playwright install-deps on Alibaba Cloud Linux

Playwright's `install-deps` uses `apt-get` (Ubuntu-only). On yum-based systems, install manually:

```bash
yum install -y nss atk at-spi2-atk cups-libs libdrm mesa-libgbm \
  libXcomposite libXdamage libXrandr alsa-lib pango gtk3 libxkbcommon
```

---

## Service Verification Checklist

Never report "it's done" without verifying:

```bash
# 1. Service running
systemctl status YOUR-SERVICE --no-pager | head -10

# 2. Port listening
ss -tlnp | grep YOUR-PORT

# 3. Local HTTP test
curl -s -o /dev/null -w "%{http_code}" http://localhost:YOUR-PORT/

# 4. Public access (through nginx)
curl -s -o /dev/null -w "%{http_code}" http://PUBLIC-IP/your-path/
```

---

## Duplicate CORS Headers

If the backend framework (FastAPI, Express, etc.) has its own CORS middleware, do NOT also add CORS headers in nginx. Browsers reject duplicate `Access-Control-Allow-Origin` headers.

**Symptoms:** `curl -i` shows header appearing twice; browser shows `TypeError: Failed to fetch`; curl/Python work fine.

**Fix:** Remove all `add_header Access-Control-Allow-*` from nginx. Let the backend handle CORS.
