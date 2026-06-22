# Static Site + External API Proxy Pattern

Deploy a static HTML/JS frontend that fetches data from external APIs, using nginx as an API reverse proxy to avoid CORS and network issues from China servers.

## When to Use

- Frontend-only sites (single HTML file, no backend server)
- Need to call external APIs (Frankfurter, exchange rates, weather, etc.)
- Server is in China and external APIs may be slow/blocked

## Architecture

```
Browser → nginx:80/fx/      → static HTML files (alias)
Browser → nginx:80/fx-api/  → nginx proxy → external API (HTTPS)
```

## Nginx Config

Add to existing `server_name <IP>` block (NOT a new `server_name _` block):

```nginx
# Static files
location /fx/ {
    auth_basic off;                    # if server has auth_basic
    alias /opt/project-name/;
    index index.html;
    try_files $uri $uri/ /fx/index.html;
    add_header Cache-Control "no-cache, must-revalidate";
}

# API reverse proxy (HTTPS upstream)
location /fx-api/ {
    auth_basic off;
    proxy_pass https://api.example.com/v1/;
    proxy_ssl_server_name on;          # REQUIRED for HTTPS SNI
    proxy_set_header Host api.example.com;
    proxy_read_timeout 15;
}
```

## Pitfalls

1. **`proxy_ssl_server_name on` is REQUIRED** for HTTPS upstream. Without it, the TLS handshake fails silently (Cloudflare returns 301 or connection reset).

2. **API domain redirects** — External APIs may redirect `.app` → `.dev` or add `/v1/` prefix. Always test the final URL with `curl -sL` first. If you get a 301, check the `Location` header and update the proxy_pass target.

3. **`alias` vs `root`** — Use `alias` for subpath (`/fx/` → `/opt/project/`). With `root`, nginx appends the location path to the root dir (`/usr/share/nginx/html/fx/`), which is wrong if files are elsewhere.

4. **File permissions** — nginx runs as `nginx` user. Static files need `644`, directories need `755`. Default `write_file` creates `600` → 403 Forbidden.

5. **auth_basic interference** — If the server block has `auth_basic`, add `auth_basic off;` to each public location block.

6. **Frontend fallback** — Configure the JS to try the proxy first, then fall back to direct API access. This way the site works both from China (via proxy) and from outside (direct):
   ```js
   const API_PROXY = '/fx-api';
   const API_DIRECT = 'https://api.example.com/v1';
   async function fetchJSON(url) {
     try {
       const r = await fetch(url);
       return await r.json();
     } catch (e) {
       if (url.includes('/fx-api/')) {
         return await fetch(url.replace('/fx-api', API_DIRECT)).then(r => r.json());
       }
       throw e;
     }
   }
   ```

## File Permissions Fix

```bash
chmod 644 /opt/project-name/index.html
chmod 755 /opt/project-name /opt/project-name/data
```

## Frankfurter API (ECB Exchange Rates)

The Frankfurter API provides free, no-key exchange rate data from the European Central Bank. **Key gotcha (as of 2026-06):** `api.frankfurter.app` redirects (301) to `api.frankfurter.dev/v1/`. The `/v1/` prefix is required on the new domain.

```bash
# Test the final URL before writing nginx config:
curl -sL "https://api.frankfurter.app/latest?from=CNY&to=JPY" -D - 2>&1 | grep -i location
# → Location: https://api.frankfurter.dev/v1/latest?from=CNY&to=JPY

# Correct nginx proxy_pass:
location /fx-api/ {
    auth_basic off;
    proxy_pass https://api.frankfurter.dev/v1/;   # trailing slash strips /fx-api/
    proxy_ssl_server_name on;
    proxy_set_header Host api.frankfurter.dev;
    proxy_read_timeout 15;
}
```

**Limitation:** ECB publishes rates once per day (around 16:00 CET, weekdays only). On weekends and ECB holidays, the latest rate stalls at the previous business day. See "Multi-Source Fallback" below for the fix.

## Multi-Source Fallback (Weekend/Holiday Data Staleness)

When the primary API (Frankfurter/ECB) goes stale on weekends, add a secondary source and auto-pick the newer one.

**Recommended secondary source: open.er-api.com**
- Free, no API key, no rate limits
- Updates daily including weekends
- Response format differs from Frankfurter — needs normalization

```nginx
# Add a second proxy location for the alt API
location /fx-api2/ {
    auth_basic off;
    proxy_pass https://open.er-api.com/v6/;
    proxy_ssl_server_name on;
    proxy_set_header Host open.er-api.com;
    proxy_read_timeout 15;
}
```

**Frontend pattern — fetch both, pick newer:**

```js
const PROXY  = '/fx-api';   // Frankfurter (ECB, weekdays)
const PROXY2 = '/fx-api2';  // open.er-api (daily including weekends)

// Fetch from alt source and normalize to frankfurter format
async function fetchLatestAlt(base) {
  const path = '/latest/' + base;
  let data;
  try {
    const r = await fetch(PROXY2 + path, {signal: AbortSignal.timeout(6000)});
    if (r.ok) data = await r.json();
  } catch(e) {}
  if (!data) {
    try {
      const r2 = await fetch('https://open.er-api.com/v6' + path, {signal: AbortSignal.timeout(10000)});
      if (r2.ok) data = await r2.json();
    } catch(e) {}
  }
  if (!data || !data.rates) return null;
  // Normalize: open.er-api uses time_last_update_utc instead of date
  const months = {Jan:'01',Feb:'02',Mar:'03',Apr:'04',May:'05',Jun:'06',
                  Jul:'07',Aug:'08',Sep:'09',Oct:'10',Nov:'11',Dec:'12'};
  let date = '';
  const m = (data.time_last_update_utc||'').match(/\d{2}\s+(\w{3})\s+(\d{4})/);
  if (m) date = m[2]+'-'+months[m[1]]+'-'+data.time_last_update_utc.slice(5,7);
  return {amount:1, base:data.base_code||base, date, rates:data.rates};
}

// Pick the response with the more recent date
function pickNewer(a, b) {
  if (!a) return b;
  if (!b) return a;
  return (a.date || '') >= (b.date || '') ? a : b;
}

// In fetchAll: request both sources in parallel
const [ffLatest, altLatest, history, ...] = await Promise.all([
  apiFetch('/latest?from=CNY&to=JPY'),        // Frankfurter
  fetchLatestAlt('CNY').catch(()=>null),        // open.er-api
  apiFetch('/'+start+'..'+end+'?from=CNY&to=JPY'), // history (Frankfurter only)
  // ... other fetches
]);
const latest = pickNewer(ffLatest, altLatest ? {amount:1,base:'CNY',date:altLatest.date,rates:{JPY:altLatest.rates.JPY}} : null);
```

**Backend (cron monitor) pattern:**

```python
def fetch_alt_latest(base: str) -> dict | None:
    """Fetch from open.er-api.com, normalize to frankfurter format."""
    try:
        data = fetch_json(f"https://open.er-api.com/v6/latest/{base}")
        if "rates" not in data: return None
        import re, calendar
        m = re.search(r"\d{2}\s+(\w{3})\s+(\d{4})", data.get("time_last_update_utc", ""))
        date_str = ""
        if m:
            months = {v: f"{k:02d}" for k, v in enumerate(calendar.month_abbr) if v}
            date_str = f"{m.group(2)}-{months.get(m.group(1), '00')}-{data['time_last_update_utc'][5:7]}"
        return {"rates": data["rates"], "date": date_str}
    except Exception:
        return None

# In main(): pick the newer source
ff_latest = fetch_json(f"{API_BASE}/latest?from=CNY&to=JPY")
alt_latest = fetch_alt_latest("CNY")
if alt_latest and alt_latest.get("date", "") > ff_latest.get("date", ""):
    current_rate = alt_latest["rates"]["JPY"]
    data_date = alt_latest["date"]
else:
    current_rate = ff_latest["rates"]["JPY"]
    data_date = ff_latest["date"]
```

**Key points:**
- Keep Frankfurter for historical data (it has the time-series API `/{start}..{end}`)
- Only use alt source for the "latest" rate display
- `pickNewer()` compares date strings (YYYY-MM-DD lexicographic = chronological)
- open.er-api response has `time_last_update_utc` (RFC 2822) not `date` — must normalize
- Test both nginx proxies: `curl -s -H "Host: PUBLIC_IP" http://127.0.0.1/fx-api2/latest/CNY`

**⚠ User preference: NO simulated/interpolated data.** PCHIP interpolation was explicitly rejected ("不用模拟"). If the user wants higher data density, find a real data source — do NOT use interpolation to fake it. If no free intraday API exists, the feature doesn't exist.

If interpolation IS acceptable for a different user/project, use monotone cubic Hermite (PCHIP) — it preserves monotonicity and doesn't overshoot. Generate ~12-48 intermediate points per day depending on zoom level.

```js
// PCHIP interpolation for sparse daily data → dense hourly-like curve
function interpolatePCHIP(dates, values, pointsPerDay) {
  const n = dates.length;
  const h = [], delta = [];
  for (let i = 0; i < n-1; i++) {
    h[i] = (parseDate(dates[i+1]) - parseDate(dates[i])) / 86400000;
    delta[i] = (values[i+1] - values[i]) / h[i];
  }
  // PCHIP slopes (Fritsch-Carlson)
  const m = new Array(n).fill(0);
  for (let i = 1; i < n-1; i++) {
    if (delta[i-1] * delta[i] <= 0) m[i] = 0;
    else m[i] = 3*(h[i-1]+h[i]) / ((2*h[i]+h[i-1])/delta[i-1] + (h[i]+2*h[i-1])/delta[i]);
  }
  // endpoints
  m[0] = ((2*h[0]+h[1])*delta[0] - h[0]*delta[1]) / (h[0]+h[1]);
  m[n-1] = ((2*h[n-2]+h[n-3])*delta[n-2] - h[n-2]*delta[n-3]) / (h[n-2]+h[n-3]);
  // generate points
  const out = { dates: [], values: [] };
  for (let i = 0; i < n-1; i++) {
    const steps = Math.max(Math.round(h[i] * pointsPerDay), 4);
    for (let j = 0; j < steps; j++) {
      const t = j / steps, t2 = t*t, t3 = t2*t;
      const h00 = 2*t3-3*t2+1, h10 = t3-2*t2+t, h01 = -2*t3+3*t2, h11 = t3-t2;
      out.values.push(+(h00*values[i] + h10*h[i]*m[i] + h01*values[i+1] + h11*h[i]*m[i+1]).toFixed(4));
      out.dates.push(fmt(new Date(parseDate(dates[i]).getTime() + h[i]*j/steps*86400000)));
    }
  }
  out.dates.push(dates[n-1]); out.values.push(values[n-1]);
  return out;
}
```

Usage: 7-day view → 24 pts/day, 30-day → 12 pts/day, 90-day → 6 pts/day. For "1-day" view, fetch 6 days for PCHIP context then slice to last 24h of interpolated points.

## Verification

```bash
# 1. Static page
curl -sI http://PUBLIC-IP/fx/ | head -2    # expect 200

# 2. API proxy
curl -s http://PUBLIC-IP/fx-api/latest?from=CNY&to=JPY  # expect JSON

# 3. Historical API
curl -s "http://PUBLIC-IP/fx-api/2026-05-22..2026-06-21?from=CNY&to=JPY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['rates']))"
```
