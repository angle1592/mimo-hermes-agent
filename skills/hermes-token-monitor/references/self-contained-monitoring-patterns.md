# Self-Contained Monitoring Web Service — Generic Patterns

Reusable patterns for deploying zero-dependency Python HTTP dashboards. These patterns are implemented concretely in the parent skill `hermes-token-monitor`.

## Architecture

```
Browser → nginx (:80) → /prefix/ → Python http.server (:8765)
                                        ↓
                                   SQLite / JSON / CLI
```

## Python HTTP Server Template

Use `http.server.ThreadingHTTPServer` with a custom `BaseHTTPRequestHandler`. Embed HTML as a Python string.

```python
#!/usr/bin/env python3
import http.server, json, sqlite3, os, time
from urllib.parse import urlparse

DB_PATH = os.path.expanduser("~/your_data.db")
HOST, PORT = "127.0.0.1", 8765

def query_data():
    """Query your data source and return dict."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT ...")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"data": rows, "updated_at": int(time.time())}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/data":
            self._json(query_data())
            return
        if path == "/api/health":
            self._json({"status": "ok"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode())

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

def main():
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
```

### Critical: Use Relative URLs in JS

```javascript
// ✅ CORRECT — works behind /prefix/ proxy
const resp = await fetch('api/data');

// ❌ WRONG — breaks behind nginx path prefix
const resp = await fetch('/api/data');
```

## Systemd Service Template

```bash
sudo tee /etc/systemd/system/my-monitor.service << 'EOF'
[Unit]
Description=My Monitor Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/app
ExecStart=/usr/bin/python3 /path/to/app/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now my-monitor
```

## Nginx Reverse Proxy with Path Prefix

### Pitfall: server_name matching

When multiple `server` blocks listen on port 80, nginx picks based on `Host` header. If no `server_name` matches exactly, nginx uses the **first** block defined as default.

**Solution**: Add `default_server` to the fallback block:
```nginx
server {
    listen 80 default_server;
    server_name _;
    # ...
}
```

### Pitfall: auth_basic inheritance

If a server block has `auth_basic`, all locations inherit it. Override with `auth_basic off;`:
```nginx
location /public-path/ {
    auth_basic off;           # MUST be first
    proxy_pass http://127.0.0.1:8765/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 86400;
}
```

After changing `auth_basic` settings, use `systemctl restart nginx` (not `reload`).

### Trailing slash in proxy_pass

- `proxy_pass http://backend/;` (with trailing slash) strips the location prefix
- `proxy_pass http://backend;` (without) keeps the full path

For path-prefix proxying, trailing slash is almost always correct:
```nginx
location /monitor/ {
    proxy_pass http://127.0.0.1:8765/;  # /monitor/api/data → /api/data
}
```

## Frontend UX: Handling Growing Datasets

### Date Grouping with Collapsible Sections

Group records by relative time labels (Today, Yesterday, This Week, Last 7 Days, Last 30 Days, Older):

```javascript
function getDateLabel(ts) {
  const d = new Date(ts * 1000);
  const today = new Date(); today.setHours(0,0,0,0);
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
  const weekStart = new Date(today); weekStart.setDate(weekStart.getDate() - today.getDay());
  const dNorm = new Date(d); dNorm.setHours(0,0,0,0);
  const diff = (today - dNorm) / 86400000;
  if (diff === 0) return '今天';
  if (diff === 1) return '昨天';
  if (dNorm >= weekStart) return '这周';
  const weekAgo = new Date(today); weekAgo.setDate(weekAgo.getDate() - 7);
  if (dNorm >= weekAgo) return '最近 7 天';
  const monthAgo = new Date(today); monthAgo.setMonth(monthAgo.getMonth() - 1);
  if (dNorm >= monthAgo) return '最近 30 天';
  return '更早';
}
```

### Filter Bar (Search + Dropdowns)

```html
<div class="filter-bar">
  <input type="text" id="search-input" placeholder="🔍 搜索..." oninput="applyFilters()">
  <select id="model-filter" onchange="applyFilters()">
    <option value="">全部模型</option>
  </select>
</div>
```

### Sort by Column

```javascript
function sortSessions(sessions, sortKey) {
  const [field, dir] = sortKey.split('-');
  const mult = dir === 'desc' ? -1 : 1;
  return [...sessions].sort((a, b) => {
    let va, vb;
    switch (field) {
      case 'time': va = a.started_at || 0; vb = b.started_at || 0; break;
      case 'cost': va = a.calculated_cost_cny || 0; vb = b.calculated_cost_cny || 0; break;
      default: va = a.started_at || 0; vb = b.started_at || 0;
    }
    return (va - vb) * mult;
  });
}
```

### Pagination with "Load More"

```javascript
const PAGE_SIZE = 20;
let shownCount = 0;

function loadMore() {
  shownCount += PAGE_SIZE;
  // re-run filtering + rendering with higher shownCount
}
```

### Backend: Remove Strict LIMIT

Fetch enough data for client-side filtering/pagination. Increase SQL LIMIT to 500+ or remove it.

## Data Integrity: Cross-Check Aggregations

### 1. Total cost vs detail scope mismatch

If "total cost" comes from summing per-row costs from `LIMIT N` query, it only covers N rows. Calculate totals from a separate `GROUP BY` aggregation over ALL rows.

### 2. Unknown values → zero (silent data loss)

When calculating derived metrics from an enum/key table, an unknown key silently produces 0. Always use a reasonable fallback, never 0.

### 3. Token/size aggregation must include all relevant columns

If data model splits counts across multiple columns, verify the schema before writing SQL. `total = col_a + col_b` may exclude `col_c`.

### 4. Hardcoded conversion rates drift silently

Search for ALL occurrences when updating:
```bash
grep -n 'OLD_VALUE' server.py
```

## Common Pitfalls

1. **`auth_basic off` not working after reload** → use `restart`, not `reload`
2. **401 on external but 200 on localhost** → check which server block matches the Host header
3. **JS fetch 404** → check relative vs absolute URLs; behind a path prefix, absolute paths break
4. **Port already in use** → check with `ss -tlnp | grep PORT`
5. **Python import errors** → server.py must run from a directory where imports resolve; use `WorkingDirectory=` in systemd
