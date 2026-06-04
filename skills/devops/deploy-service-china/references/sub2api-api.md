# Sub2API API Reference

## Authentication

```bash
# Login (endpoint: /api/v1/auth/login)
TOKEN=$(curl -s -X POST http://127.0.0.1:8090/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@sub2api.local","password":"YOUR_PASSWORD"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['access_token'])")
```

**Pitfall**: The login endpoint is `/api/v1/auth/login`, NOT `/api/auth/login` or `/auth/login`. The latter returns 200 but doesn't return a token.

## Account Import Format

Accounts can be imported as JSON. The format uses `accounts` array with OAuth credentials:

```json
{
  "exported_at": "2026-06-04T05:38:58.525Z",
  "proxies": [],
  "accounts": [
    {
      "name": "email@example.com",
      "platform": "openai",
      "type": "oauth",
      "credentials": {
        "access_token": "eyJ...",
        "refresh_token": "rt.1.AAA...",
        "chatgpt_account_id": "...",
        "chatgpt_user_id": "user-...",
        "organization_id": "org-...",
        "client_id": "app_...",
        "email": "...",
        "expires_at": 1781407215
      },
      "extra": { ... },
      "concurrency": 10,
      "priority": 1,
      "rate_multiplier": 1,
      "auto_pause_on_expired": true
    }
  ]
}
```

Import via the web UI (账号管理 → 导入) rather than API (the import API endpoint is not documented).

## Common API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/auth/login` | POST | No | Login, returns access_token |
| `/health` | GET | No | Health check |
| `/openapi.json` | GET | No | Returns frontend HTML (not actual OpenAPI spec) |

**Pitfall**: `/openapi.json` returns 200 but serves the SPA frontend HTML, not an API spec. Don't use it for API discovery.

## Checking Service Health

```bash
# Direct
curl -s http://127.0.0.1:8090/health

# Via nginx
curl -s -H "Host: YOUR_SERVER_IP" http://127.0.0.1/sub2api/health

# From container
docker exec sub2api wget -q -T 5 -O /dev/null http://localhost:8080/health
```
