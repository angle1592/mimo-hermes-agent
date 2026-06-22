# SillyTavern + PM2 Deployment

SillyTavern (酒馆) is a Node.js frontend for LLM chat. Deploy with PM2 for process management.

## Install

```bash
cd /opt
git clone https://github.com/SillyTavern/SillyTavern.git --depth 1
cd SillyTavern
npm install --production    # or: npm install (full, includes devDeps)
```

## Config (`config.yaml`)

Key settings to change for server deployment:

```yaml
listen: true          # listen on all interfaces (default: false = localhost only)
port: 8002            # avoid 8000 (often taken by FastAPI/posture-monitor)
browserLaunch:
  port: -1            # disable browser auto-launch on headless server
```

### Security Configuration (CRITICAL)

SillyTavern REQUIRES at least one security measure when `listen: true` (non-localhost). Three options:

**Option 1: Basic Auth (recommended for simple setups)**
```yaml
listen: true
whitelistMode: false
basicAuthMode: true
basicAuthUser:
  username: "admin"
  password: "YOUR_STRONG_PASSWORD"
```

**Option 2: Whitelist mode (for known IPs only)**
```yaml
listen: true
whitelistMode: true
whitelist:
  - "127.0.0.1"
  - "::1"
  - "YOUR.IP.ADDRESS"
```

**Option 3: User accounts (built-in auth system)**
Enable `enableUserAccounts: true` in config.yaml.

## Start with PM2

```bash
cd /opt/SillyTavern
npx pm2 start server.js --name sillytavern
npx pm2 save
npx pm2 startup    # generates systemd unit for pm2-daemon auto-start
```

### PM2 vs systemd

PM2 is preferred for Node.js apps over raw systemd because:
- Built-in log rotation and crash restart
- `pm2 save` / `pm2 startup` handles boot persistence
- `pm2 logs`, `pm2 monit` for quick debugging

But systemd is fine too if PM2 is not installed.

## Pitfalls

1. **Port 8000 conflict** — FastAPI services (posture-monitor, etc.) often bind port 8000. Always check `ss -tlnp | grep PORT` before configuring.
2. **First boot slow** — SillyTavern compiles frontend libraries on first start (~10-20s). Don't assume it's broken if port isn't listening immediately. Wait 20s, then check PM2 logs: `npx pm2 logs sillytavern --lines 10 --nostream`.
3. **WebSocket support required** — SillyTavern uses WebSocket for streaming. Nginx proxy MUST include `Upgrade` and `Connection` headers:
   ```nginx
   proxy_http_version 1.1;
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection "upgrade";
   ```
4. **No subpath support** — SillyTavern doesn't support `basePath` config. Must proxy at root (`location /`) on its own port, or use a dedicated nginx server block.
5. **Cookie secret auto-generated** — First run generates a cookie secret in data root. This is normal, not an error.
6. **Security group** — Like all non-standard ports, needs explicit opening in Alibaba Cloud security group. Default port 8002 won't be accessible externally without this.
7. **CRITICAL: whitelistMode + listen:true = crash loop** — SillyTavern REQUIRES at least one security measure when `listen: true` (non-localhost). If you set `whitelistMode: false` without enabling anything else, the server crashes in a restart loop (PM2 shows restart count climbing, 100% CPU). Error: "Your current SillyTavern configuration is insecure (listening to non-localhost)."
   - **Wrong:** `whitelistMode: false` alone → crash loop
   - **Wrong:** `whitelistMode: true` with no IPs added → 403 Forbidden for all external users
   - **Right:** Enable `basicAuthMode: true` with username/password, then disable whitelist
   - After changing config, must restart: `npx pm2 restart sillytavern`
   - First boot after auth change takes ~30s (frontend recompilation). Wait before testing.
8. **Config file has misleading commented-out examples** — The default `config.yaml` has `basicAuthUser` with `username: "user"` and `password: "password"` as commented examples. These are NOT active unless `basicAuthMode: true` is explicitly set. Don't assume auth is configured just because you see credentials in the file.

## Quick Commands

```bash
npx pm2 status                    # check running status
npx pm2 logs sillytavern --lines 20 --nostream   # view logs
npx pm2 restart sillytavern       # restart
npx pm2 stop sillytavern          # stop
```

## Nginx Config (Dedicated Port)

```nginx
server {
    listen EXTERNAL_PORT;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }
}
```
