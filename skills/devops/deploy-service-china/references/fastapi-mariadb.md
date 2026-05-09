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

### Pitfall: APScheduler Interval — Check the Actual Code, Not Just Comments

The `scheduler.add_job(..., seconds=N)` value is what controls the interval, NOT the docstring or log message. In the posture-monitor project, the docstring said "每 10 秒" but the actual code was `seconds=1`. When changing the polling interval, update **both** the `seconds=` parameter and the surrounding comments/log messages to stay in sync.

```python
# WRONG — comment says 10s but code says 1s
"""每 10 秒从 OneNET 拉取"""
scheduler.add_job(sync_once, "interval", seconds=1, ...)  # ← actual is 1s!

# RIGHT — comment, code, and log all match
"""每 10 秒从 OneNET 拉取"""
scheduler.add_job(sync_once, "interval", seconds=10, ...)
logger.info("[Sync] Background sync started (interval=10s)")
```

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

### Pitfall: No CORS Headers in Nginx When FastAPI Has CORSMiddleware

FastAPI's `CORSMiddleware` already handles CORS (origin, methods, headers, preflight). Do NOT add `add_header Access-Control-Allow-*` in nginx — browsers reject responses with duplicate CORS headers. See the main SKILL.md "Duplicate CORS Headers" pitfall for details.

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
# 3-week demo data with improvement arc (best for defense demos)
python3 ~/.hermes/skills/devops/deploy-service-china/scripts/seed-posture-data.py \
  --days 21 --sql-file /tmp/seed.sql
mysql -u root < /tmp/seed.sql

# Custom range
python3 scripts/seed-posture-data.py --days 14 --start-date 2026-05-01 -o /tmp/seed.sql
```

The script generates a **3-week improvement trend** (score 55→75→85), making it ideal for thesis defense presentations. Each day has unique posture distributions, weekday/weekend differences, and fatigue-based degradation.

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

THINGMODEL_BASE = "https://iot-api.heclouds.com/thingmodel"

def _headers():
    return {"authorization": settings.onenet_token, "Content-Type": "application/json"}

async def query_device_properties():
    """查询设备最新全部属性 (GET)."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{THINGMODEL_BASE}/query-device-property",
            params={"product_id": pid, "device_name": name},
            headers=_headers(),
        )
        return resp.json().get("data", [])

async def set_device_property(params: dict) -> dict:
    """向设备下发属性设置指令 (POST).

    OneNET API: POST /thingmodel/set-device-property
    Returns {"ok": bool, "code": int, "msg": str}
    """
    payload = {"product_id": pid, "device_name": name, "params": params}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{THINGMODEL_BASE}/set-device-property",
            json=payload, headers=_headers(),
        )
        body = resp.json()
    code = body.get("code", -1)
    if code == 0:
        return {"ok": True, "code": 0}
    return {"ok": False, "code": code, "msg": body.get("msg", "")}
```

### Pitfall: Missing `__init__.py` After Git Reset

When doing `git reset --hard` to a commit that removed the server directory, Python module files (`__init__.py`, `main.py`, service files) are lost. The app fails to start with:

```
ERROR: Error loading ASGI app. Could not import module "app.main"
```

**Fix:** Restore the missing module files from the old commit:

```bash
cd /path/to/repo
git checkout OLD_COMMIT -- server/app/__init__.py server/app/main.py \
  server/app/routers/__init__.py server/app/services/__init__.py server/app/services/onenet.py
rm -rf server/app/__pycache__ server/app/routers/__pycache__ server/app/services/__pycache__
systemctl restart posture-monitor.service
```

**General pattern:** When selectively re-adding files to a reset branch, always check that the Python module structure is complete (`__init__.py` in every package directory, `main.py` for the app entry point, and any imports the added files depend on).

### Pitfall: FastAPI `HTTPException` with dict detail

When returning structured error info via `raise HTTPException(400, detail={...})`, the `detail` must be passed as a keyword argument. Passing the dict positionally works but is fragile:

```python
# WRONG — positional, hard to read
raise HTTPException(400, {"ok": False, "code": code, "msg": msg})

# RIGHT — explicit keyword
raise HTTPException(400, detail={"ok": False, "code": code, "msg": msg})
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

## Session-Based Duration Calculation (good_posture_minutes)

The naive approach (`record_count * 10 / 60`) produces unrealistic durations (900+ minutes/day) because simulated data has no gaps. Real posture monitoring is intermittent — users sit for 1-2 hour sessions with breaks.

**Algorithm:**
1. Filter: only `person_present=true` with scored posture types (`normal`, `head_down`, `hunchback`)
2. Sort by `onenet_time`
3. Split into sessions: gap > 5 minutes between consecutive records = new session
4. Session duration = `last_record.time - first_record.time` (min: `record_count * 10s`)
5. `good_minutes = sum(session_duration * healthy_count / scored_count)` for each session

**Why 5 minutes?** Short enough to catch real breaks (bathroom, coffee), long enough to not split a continuous study session due to occasional network hiccups.

**Effect:**
- 100 records across 8h → ~4h session → ~2-3h good minutes (reasonable)
- Continuous 16h simulated data → 1 session → ~972 minutes (data problem, not algorithm)
- Real device data with natural breaks → multiple short sessions → realistic totals

```python
# Key code pattern in daily_stats:
SESSION_GAP_MINUTES = 5
sessions = [[records[0]]]
for r in records[1:]:
    gap = (r.onenet_time - sessions[-1][-1].onenet_time).total_seconds()
    if gap > SESSION_GAP_MINUTES * 60:
        sessions.append([])
    sessions[-1].append(r)
```

## Health Score Algorithm & Targeted Data Insertion

The posture monitor calculates `health_score` as:

```
score = round(normal_count / (normal_count + head_down_count + hunchback_count) * 100)
```

**Key:** `no_person` and `unknown` posture types are **excluded** from the score calculation (they don't count toward the denominator). Only `normal`, `head_down`, and `hunchback` matter.

### Quick Score Reference

| Target Score | normal | head_down | hunchback | Total scored |
|---|---|---|---|---|
| 50 | 50 | 25 | 25 | 100 |
| 60 | 60 | 20 | 20 | 100 |
| 70 | 70 | 20 | 10 | 100 |
| 80 | 80 | 10 | 10 | 100 |
| 90 | 90 | 5 | 5 | 100 |

### Direct SQL Insertion for Exact Scores

When the seed script's improvement arc (55→75→85) doesn't fit and you need exact scores for specific dates, insert directly via SQL:

```python
# Generate records spaced ~10s apart starting at 08:00
# For score 70: 70 normal + 20 head_down + 10 hunchback
def gen_records(date, normal_n, down_n, hunch_n):
    types = ["normal"] * normal_n + ["head_down"] * down_n + ["hunchback"] * hunch_n
    interval = max(10, 28800 // len(types))  # spread across 8h
    rows = []
    for i, pt in enumerate(types):
        secs = 8 * 3600 + i * interval
        h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
        ts = f"{date} {h:02d}:{m:02d}:{s:02d}"
        rows.append(f"('main','{pt}',1,{300 + (i%5)*50},0,'{ts}','{ts}')")
    return rows
```

```bash
# Insert via mysql CLI (use root — no password on socket)
mysql -u root -e "INSERT IGNORE INTO posture_monitor.posture_records \
  (device_id,posture_type,person_present,ambient_lux,fill_light_on,onenet_time,created_at) \
  VALUES ('main','normal',1,350,0,'2026-05-10 08:00:00','2026-05-10 08:00:00'),(...);"

# Verify via API
curl -s http://127.0.0.1:8000/api/posture/stats/daily?date=2026-05-10
# → {"good_posture_minutes":12,"abnormal_count":30,"health_score":70}
```

**Pitfall:** Use `INSERT IGNORE` because the table has a `UniqueConstraint("device_id", "onenet_time")` — duplicate timestamps silently skip instead of erroring.

**Pitfall:** Use `mysql -u root` (no `-p`) for local socket auth. The `posture_user` account is bound to `'127.0.0.1'` (TCP only), so `mysql -u posture_user -p'pass'` without `-h 127.0.0.1` fails with "Access denied".

## Troubleshooting: OneNET Auth Failures

When `10403 authentication failed` occurs, follow this sequence:

1. **Verify token format** — must be `version=2018-10-31&res=...&et=...&method=md5&sign=...`
2. **Check expiry** — decode `et` timestamp: `python3 -c "from datetime import datetime; print(datetime.fromtimestamp(ET_VALUE))"`
3. **Verify signature** — generate a new token from the access key and compare `sign` values. If they don't match, the key is wrong.
4. **Don't guess keys** — OneNET has master API keys, product API keys, and device tokens. They are NOT interchangeable. The access key from "产品概况" may not have thingmodel API permissions.
5. **Get the working token from the browser** — fastest path: ask user to run the App locally (`npm run dev:h5`), open F12 Network tab, trigger any OneNET request, and copy the `authorization` header value. This is guaranteed to work since the App already uses it.
