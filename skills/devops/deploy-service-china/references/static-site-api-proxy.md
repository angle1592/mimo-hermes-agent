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

**Limitation:** ECB publishes rates once per day (around 16:00 CET, weekdays only). No free API provides hourly/intraday CNY/JPY data without registration. Alpha Vantage demo key is rate-limited, Twelve Data requires paid key.

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
