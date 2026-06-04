# Sub2API Deployment Reference

## Overview

Sub2API is an open-source AI API gateway (⭐25k+) that converts Claude/OpenAI/Gemini subscriptions into OpenAI-compatible API endpoints. Supports multi-account management, billing, load balancing.

- GitHub: https://github.com/Wei-Shaw/sub2api
- Stack: Go backend + Vue 3 frontend + PostgreSQL 15+ + Redis 7+
- License: LGPL-3.0

## Deployed Setup (Alibaba Cloud 2GB)

Location: `/opt/sub2api/` (Docker Compose)

| Container | Image | Memory Limit | Port |
|-----------|-------|-------------|------|
| sub2api | weishaw/sub2api:latest | 512MB | 0.0.0.0:8090→8080 |
| sub2api-postgres | postgres:16-alpine | 300MB | internal only |
| sub2api-redis | redis:7-alpine | 128MB | internal only |

Nginx: `/sub2api/` path proxied to `127.0.0.1:8090` (auth_basic off, in hermes-dashboard.conf)
Public URL: http://YOUR_SERVER_IP:8090 (direct) or http://YOUR_SERVER_IP/sub2api/ (nginx)

## Key Configuration

```yaml
# docker-compose.yml key sections for 2GB server

# PostgreSQL tuning (via command override)
command: >
  postgres
    -c shared_buffers=64MB
    -c effective_cache_size=128MB
    -c maintenance_work_mem=16MB
    -c work_mem=2MB
    -c max_connections=100
    -c wal_buffers=2MB
    -c max_wal_size=256MB

# Redis memory limit
command: >
  redis-server
    --maxmemory 80mb
    --maxmemory-policy allkeys-lru

# shm_size for PostgreSQL
shm_size: 64mb
```

## Pitfalls

1. **PostgreSQL 16-alpine PGDATA** — Must set `PGDATA=/var/lib/postgresql/data` explicitly, otherwise Docker volume mount doesn't persist data and `docker compose down/up` reinitializes the DB.

2. **JWT_SECRET auto-generated** — If left empty, a random secret is generated on each restart, invalidating all login sessions. Set a fixed secret: `openssl rand -hex 32`.

3. **Admin password shown only once** — Auto-generated in logs on first run. Check: `docker logs sub2api 2>&1 | grep "Generated admin password"`. Save immediately.

4. **UPDATE_PROXY_URL for Docker containers** — Containers use bridge networking, so `127.0.0.1:7890` (mihomo) is not reachable. Use Docker gateway IP: `http://172.17.0.1:7890`.

5. **Port conflict with FileBrowser** — FileBrowser uses port 8080. Sub2API defaults to 8080 too. Change to 8090 or another free port.

6. **`postgres:18-alpine` vs `postgres:16-alpine`** — The official docker-compose.yml uses postgres:18-alpine which may not be widely available yet. Use postgres:16-alpine for reliability.

7. **Upstream API proxy (OpenAI/Claude access from China)** — `UPDATE_PROXY_URL` only covers GitHub updates. For the app itself to reach foreign APIs (OpenAI, Claude, Gemini), add `HTTP_PROXY`/`HTTPS_PROXY` as container environment variables pointing to the Docker gateway proxy:
   ```yaml
   environment:
     - HTTP_PROXY=http://172.17.0.1:7890
     - HTTPS_PROXY=http://172.17.0.1:7890
     - NO_PROXY=localhost,127.0.0.1,postgres,redis
   ```
   Verify from inside the container: `docker exec sub2api sh -c 'curl -s -x $HTTPS_PROXY https://api.openai.com'` — should return OpenAI welcome message. Note: `wget` doesn't respect HTTP_PROXY env vars for HTTPS; use `curl -x` to test.

8. **Go apps may not use env proxy for all requests** — Even with `HTTP_PROXY`/`HTTPS_PROXY` set, Sub2API (Go) may not route upstream API calls through the proxy. Create a **Proxy entry** in Sub2API admin (Settings → Proxies) with `{protocol: http, host: 172.17.0.1, port: 7890}` and assign it to each account via `proxy_id`.

9. **RUN_MODE=standard requires balance** — In standard mode, users need balance > 0 to make requests. Set `RUN_MODE=simple` for personal/self-use deployments to skip billing entirely.

10. **OAuth account import flow** — Sub2API needs accounts assigned to channels, channels linked to groups, and API keys assigned to groups. The full flow:
    1. `POST /api/v1/admin/accounts` — create account with OAuth credentials
    2. `POST /api/v1/admin/proxies` — create proxy entry (if needed)
    3. `PUT /api/v1/admin/accounts/:id` — assign `proxy_id` to account
    4. `POST /api/v1/admin/channels` — create channel, link `account_ids` and `group_ids`
    5. `PUT /api/v1/keys/:id` — set `group_id` on API key
    6. Test: `curl -X POST http://HOST:PORT/v1/chat/completions -H "Authorization: Bearer sk-..." -d '{"model":"gpt-4o-mini","messages":[...]}'`

11. **API key group mismatch** — Default API key group is `anthropic`. For OpenAI accounts, must update key's `group_id` to the `openai-default` group (ID 4 by default). Wrong group → "No available accounts".

## Template

See `templates/sub2api-docker-compose.2g-ram.yml` for a ready-to-use memory-optimized compose file.

## Maintenance

Key settings in `/opt/sub2api/.env`:
- `POSTGRES_PASSWORD` — DB password
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — Admin login (auto-generated if empty)
- `JWT_SECRET` — Session persistence (set fixed value)
- `UPDATE_PROXY_URL` — GitHub proxy for updates (use Docker gateway IP)
- `RUN_MODE` — `standard` (full SaaS) or `simple` (self-use, no billing)
- `SECURITY_URL_ALLOWLIST_ALLOW_PRIVATE_HOSTS=true` — Required for local network upstreams

## Maintenance

```bash
# View logs
docker logs sub2api --tail 50

# Restart
cd /opt/sub2api && docker compose restart

# Update to latest
cd /opt/sub2api && docker compose pull && docker compose up -d

# Backup PostgreSQL
docker exec sub2api-postgres pg_dump -U sub2api sub2api > /tmp/sub2api-backup.sql
```
