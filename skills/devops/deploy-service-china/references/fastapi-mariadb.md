# FastAPI + MariaDB Service Deployment on Alibaba Cloud

Repeatable pattern for deploying Python FastAPI services with MariaDB on this server.

## Environment

- MariaDB 10.6 already installed and running (`systemctl status mariadb`)
- **MariaDB, not MySQL:** Alibaba Cloud Linux's default yum repo only has MariaDB (`yum install mariadb-server`). This is normal and expected — MariaDB is a drop-in MySQL replacement (same PyMySQL driver, same SQL, same SQLAlchemy). Do NOT try to install "real MySQL" unless the user specifically requests it; it adds complexity with zero benefit for typical workloads.
- Python 3.11 available (Alibaba Cloud Linux 4)
- Virtual environments in `server/venv/`

## Step 1: Database Setup

```bash
# Login
mysql -u root

# Create database and user
CREATE DATABASE IF NOT EXISTS app_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'app_user'@'127.0.0.1' IDENTIFIED BY 'STRONG_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE ON app_db.* TO 'app_user'@'127.0.0.1';
FLUSH PRIVILEGES;

# Apply schema
mysql -u root app_db < schema.sql
```

### Pitfall: MariaDB User Host

MariaDB treats `'user'@'localhost'` and `'user'@'127.0.0.1'` as different accounts. FastAPI with PyMySQL connects via TCP (127.0.0.1), so create the user with `'127.0.0.1'`, not `'localhost'`.

### Pitfall: `mysql` CLI Without `-h` Defaults to Socket

When the user is created for `'127.0.0.1'`, running `mysql -u user -p'pass' db` **without `-h 127.0.0.1`** connects via Unix socket (treated as `localhost`), which is a different account → `Access denied`. Always pass `-h 127.0.0.1`:

```bash
# WRONG — connects via socket as 'localhost'
mysql -u posture_user -p'PASS' posture_monitor

# RIGHT — connects via TCP as '127.0.0.1'
mysql -u posture_user -p'PASS' -h 127.0.0.1 posture_monitor
```

### Pitfall: .env Password Doesn't Match MariaDB

If the `.env` password works for the app but `mysql -u user -p'PASS'` gives `Access denied`, the password in MariaDB may have been set differently (e.g., created with a different password, or ALTER USER was run). Fix by resetting from root:

```bash
mysql -u root -e "ALTER USER 'app_user'@'127.0.0.1' IDENTIFIED BY 'PASSWORD_FROM_ENV'; FLUSH PRIVILEGES;"
```

Then verify with the `-h 127.0.0.1` form (see above).

## Step 2: Python venv + Dependencies

```bash
cd server/
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Pitfall: httpx + APScheduler Compatibility

If using APScheduler 3.x with `AsyncIOScheduler`, ensure the sync function is `async` and uses `httpx.AsyncClient`. Mixing sync `requests` in an async scheduler blocks the event loop.

## Step 3: Environment Config

```bash
# Create .env from template
cp .env.example .env
# Edit with real values — NEVER commit .env
```

## Step 4: Run with Uvicorn

```bash
# Development
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production (behind nginx — bind to localhost only for security)
# Use `python -m uvicorn` for more reliable module resolution
ExecStart=/path/to/server/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Pitfall: Background Tasks in Uvicorn

FastAPI `lifespan` context manager works correctly with uvicorn. APScheduler `AsyncIOScheduler` starts on app startup and shuts down on app shutdown. No extra signal handling needed.

## Step 5: Systemd Service

```bash
cat > /etc/systemd/system/posture-api.service << 'EOF'
[Unit]
Description=Posture Monitor API
After=network.target mariadb.service

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/server
ExecStart=/path/to/server/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5
EnvironmentFile=/path/to/server/.env

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable posture-api
systemctl start posture-api
```

### Pitfall: `After=mariadb.service`

Always add `After=mariadb.service` (or `mysql.service`) so the API doesn't start before the database is ready. Without this, the first health check may fail and systemd may restart the service unnecessarily.

## Step 6: Nginx Reverse Proxy

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Testing Checklist

```bash
# 1. Health check
curl -s http://localhost:8000/health
# Expect: {"status":"ok","database":"ok","env":"development"}

# 2. API endpoint
curl -s http://localhost:8000/api/posture/latest

# 3. Public access (after nginx)
curl -s http://PUBLIC-IP/api/posture/latest
```

## Data Seeding for Development

For IoT/monitoring projects, use `scripts/seed-posture-data.py` to generate realistic test data:

```bash
# Generate and insert directly
python3 ~/.hermes/skills/devops/deploy-service-china/scripts/seed-posture-data.py --days 7 \
  | mysql -u posture_user -p'PASS' -h 127.0.0.1 posture_monitor

# Or write to file first for review
python3 scripts/seed-posture-data.py --days 14 -o /tmp/seed.sql
```

## Common FastAPI Patterns Used

### Lifespan for Background Tasks

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_background_task()  # e.g., APScheduler
    yield
    stop_background_task()

app = FastAPI(lifespan=lifespan)
```

### OneNET IoT API Client Pattern

```python
import httpx

async def query_device_properties():
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://iot-api.heclouds.com/thingmodel/query-device-property",
            params={"product_id": pid, "device_name": name},
            headers={"authorization": token},
        )
        return resp.json().get("data", [])
```

### Pitfall: OneNET Authentication — Device Token ≠ API Token

OneNET has **multiple token types** that are NOT interchangeable:

| Token Type | Format | Used For |
|---|---|---|
| **Device Token** | `version=2018-10-31&res=products%2F...&et=...&method=md5&sign=...` | ESP32/MQTT device connection |
| **Access Key** | `E1PHvf1D/SXlSTfdB7cBX+e1u68...` (base64) | Generating signed tokens |
| **API Token (authorization)** | Generated from Access Key via HMAC-MD5 signing | HTTP API queries (`iot-api.heclouds.com`) |

**Common mistake:** Taking the device token from MQTT config and using it as `authorization` header for HTTP API → `10403 authentication failed: invalid authorization`.

**Token generation algorithm (from access key):**
```python
import base64, hmac, hashlib, time, urllib.parse

def generate_onenet_token(access_key: str, product_id: str, device_name: str, expire_seconds: int = 86400 * 30) -> str:
    et = str(int(time.time()) + expire_seconds)
    res = f"products/{product_id}/devices/{device_name}"
    string_to_sign = f"\nmd5\n{et}\n{res}\n"
    key_bytes = base64.b64decode(access_key)
    sign = base64.b64encode(hmac.new(key_bytes, string_to_sign.encode(), hashlib.md5).digest()).decode()
    return f"version=2018-10-31&res={urllib.parse.quote(res, safe='')}&et={et}&method=md5&sign={urllib.parse.quote(sign, safe='')}"
```

**If the generated token still returns `10403`:** The access key may not have permission for the `thingmodel` API. Check in OneNET console → Product → API permissions. The key needs "物模型管理" (thing model) permission scope. The user's App `.env` file (`VITE_ONENET_TOKEN`) contains the working token — ask the user for that value instead of trying to reconstruct from the access key.

### Pitfall: OneNET Property Names Are CamelCase, Values Are Strings

OneNET `query-device-property` returns identifiers in **camelCase** (e.g. `postureType`, `personPresent`, `ambientLux`, `fillLightOn`), NOT the underscore format you might expect from database columns.

**More critically:** numeric properties are returned as **strings**. `postureType` with `data_type: int32` still returns `value: "2"` (string), not `2` (int). Always `int()` cast before comparing:

```python
# WRONG — isinstance check fails because value is "2" (str)
if isinstance(value, (int, float)):
    posture_name = POSTURE_MAP.get(int(value), "unknown")

# RIGHT — always try int() conversion
try:
    posture_name = POSTURE_MAP.get(int(value), "unknown")
except (ValueError, TypeError):
    pass
```

**Property identifier mapping (for posture-monitor-system):**

| OneNET identifier | DB column | Type | Values |
|---|---|---|---|
| `postureType` | `posture_type` | str→str | `"0"`=normal, `"1"`=head_down, `"2"`=hunchback |
| `personPresent` | `person_present` | str→bool | `"true"`/`"false"` |
| `ambientLux` | `ambient_lux` | str→float | light sensor value |
| `fillLightOn` | `fill_light_on` | str→bool | `"true"`/`"false"` |

Boolean values may also arrive as strings `"true"`/`"false"` — handle both cases.

## Troubleshooting: OneNET Auth Failures

When `10403 authentication failed` occurs, follow this sequence:

1. **Verify token format** — must be `version=2018-10-31&res=...&et=...&method=md5&sign=...`
2. **Check expiry** — decode `et` timestamp: `python3 -c "from datetime import datetime; print(datetime.fromtimestamp(ET_VALUE))"`
3. **Verify signature** — generate a new token from the access key and compare `sign` values. If they don't match, the key is wrong.
4. **Don't guess keys** — OneNET has master API keys, product API keys, and device tokens. They are NOT interchangeable. The access key from "产品概况" may not have thingmodel API permissions.
5. **Get the working token from the browser** — fastest path: ask user to run the App locally (`npm run dev:h5`), open F12 Network tab, trigger any OneNET request, and copy the `authorization` header value. This is guaranteed to work since the App already uses it.
