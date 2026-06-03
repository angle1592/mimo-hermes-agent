---
name: hermes-token-monitor
description: "Deploy a real-time web dashboard for monitoring Hermes Agent token usage, costs, and cache hit rates."
version: 1.0.0
category: devops
tags: [hermes, monitoring, dashboard, token, cost, nginx, systemd]
---

# Hermes Token Monitor

Deploy a self-hosted web dashboard that displays real-time Hermes Agent token usage, cache hit rates, and cost estimates based on model-specific pricing.

## What it provides

- 📊 Total tokens, input/output breakdown
- 💾 Cache hit rate (per session and aggregate)
- 💰 Cost estimates from official API pricing
- 📋 Per-session details with model, source, tokens, hit rate, cost
- 🤖 Per-model aggregation
- 🔄 Auto-refresh every 10 seconds
- 📱 Mobile responsive

## Architecture

```
Browser → Nginx (port 80) → Python HTTP server (127.0.0.1:8765) → state.db (SQLite)
```

> **Generic monitoring patterns** (Python HTTP server template, systemd service, nginx proxy, frontend UX patterns) are documented in `references/self-contained-monitoring-patterns.md`.

- Python server: `~/.hermes/token_monitor/server.py`
- Systemd service: `hermes-token-monitor`
- Nginx proxy: `/token/` location → `http://127.0.0.1:8765/`

## Deployment Steps

### 1. Create the server script

Save the canonical `scripts/token_monitor.py` (from this repo) to `~/.hermes/token_monitor/server.py`. The script:
- Serves an HTML dashboard at `/`
- Provides JSON API at `/api/data`
- Queries `~/.hermes/state.db` for session data
- Calculates costs based on model pricing (see `docs/shared/model-pricing.md`)

> **Note:** `references/server.py` in this skill directory is a pointer — the canonical implementation lives at `scripts/token_monitor.py`.

### 2. Set up systemd service

```bash
sudo tee /etc/systemd/system/hermes-token-monitor.service << 'EOF'
[Unit]
Description=Hermes Token Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/.hermes/token_monitor
Environment=HOME=/root
ExecStart=/usr/bin/python3 /root/.hermes/token_monitor/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now hermes-token-monitor
```

### 3. Configure nginx

Add a `/token/` location block. Two scenarios:

**A. If there's an existing server block with auth_basic**, add `auth_basic off;`:
```nginx
location /token/ {
    auth_basic off;
    proxy_pass http://127.0.0.1:8765/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 86400;
}
```

**B. If using a default server block**, just the proxy is enough:
```nginx
location /token/ {
    proxy_pass http://127.0.0.1:8765/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 86400;
}
```

**Important:** If the parent `server` block has `server_name <specific_ip>` and you also want it accessible at the default hostname, add `default_server` to the default block's `listen` directive:
```nginx
server {
    listen 80 default_server;
    ...
}
```

After nginx config changes, **restart** (not reload) if you changed `auth_basic` settings:
```bash
sudo nginx -t && sudo systemctl restart nginx
```

### 4. Verify

```bash
# Check service
systemctl status hermes-token-monitor

# Test API
curl -s http://127.0.0.1/token/api/data | python3 -m json.tool | head -20

# Test page
curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1/token/
```

Access at `http://<server-ip>/token/`

## Exchange Rate

The panel hardcodes `USD_TO_CNY` at the top of server.py. Check the live rate periodically:

```bash
curl -s "https://open.er-api.com/v6/latest/USD" | python3 -c "import sys,json; print(json.load(sys.stdin)['rates'].get('CNY'))"
```

Update the `USD_TO_CNY` constant in server.py and restart. Also update any hardcoded `usdToCny` in the embedded JavaScript (search for the old value in the HTML template):

```bash
sudo systemctl restart hermes-token-monitor
```

## Frontend UX — Handling Large Session Lists

As sessions accumulate, a flat table becomes unusable. The dashboard implements patterns inspired by Grafana, Datadog, Linear, and Vercel Analytics:

### Architecture: Client-side rendering of all data

The backend removes the old `LIMIT 50` and instead fetches up to 500 sessions. All filtering, grouping, sorting, and pagination happens client-side in JavaScript — no backend API changes needed for UX features.

### UX Features (all pure JS, no dependencies)

| Feature | How it works | Inspiration |
|---------|-------------|-------------|
| **Date grouping** | Sessions auto-grouped as 今天/昨天/这周/最近7天/最近30天/更早 via `getDateLabel()` | Linear activity log, iOS notifications |
| **Collapsible groups** | Click header to expand/collapse via `toggleGroup()` | Standard UI pattern |
| **Per-group summary** | Each group header shows count + total cost | Vercel Analytics |
| **Search** | Free-text search across session_id, source, model name | Datadog Log Explorer |
| **Model/source filter** | Dropdowns populated dynamically from data | Grafana Explore |
| **Sort** | By time (asc/desc), cost (asc/desc), output tokens (asc/desc) | Notion/Linear tables |
| **Load more** | Paginated in chunks of `PAGE_SIZE` (20), with "还有 N 条" button | Universal |
| **Filter count** | Badge shows "X 条记录" after filtering | Standard |

### Implementation Notes

1. **Backend**: Remove `LIMIT 50` → `LIMIT 500` from the sessions SQL query. Send all sessions to the frontend.
2. **Global state**: Store sessions in `allSessions` array. `render()` populates it, `applyFilters()` filters + renders.
3. **Filter re-entry**: When user types in search or changes dropdown, `applyFilters()` re-runs. Use `oninput` for search (real-time), `onchange` for selects.
4. **Load more**: Clicking increases `shownCount` by `PAGE_SIZE` and re-renders. Sorted/filtered state is preserved because `loadMore()` re-reads current filter values.
5. **Group collapse state**: Groups default to `open`. Toggle via CSS class on the body div + chevron rotation.

### Key CSS classes

```css
.date-group          /* Wrapper per date bucket */
.date-group-header   /* Clickable header with label + summary */
.date-group-body     /* Hidden by default, .open to show */
.filter-bar          /* Row of input + selects */
.load-more           /* Dashed border button at bottom */
```



### Adding RMB (CNY) display — CNY as primary unit

Users in China may want costs displayed in RMB instead of USD. Implement it with CNY as the primary unit:

1. Add a `USD_TO_CNY` constant at the top of server.py (check live rate):
```python
USD_TO_CNY = 6.85  # Check live rate periodically
```

2. Return `cost_cny` alongside `cost` from `calc_cost()`:
```python
return {
    "cost": round(cost, 6),
    "cost_cny": round(cost * USD_TO_CNY, 6),
    # ...
}
```

3. Create a `fmt_cost_cny()` helper and use it for all cost values:
```javascript
function fmtCostCNY(cny) {
  if (cny == null || cny === 0) return '¥0.00';
  if (cny < 0.01) return '¥' + cny.toFixed(6);
  if (cny < 1) return '¥' + cny.toFixed(4);
  if (cny < 100) return '¥' + cny.toFixed(2);
  return '¥' + cny.toFixed(2);
}
```

4. Update stat cards, session table, and model table to use CNY throughout. The USD equivalent can be shown as small secondary text (e.g. `≈ $0.14`).

5. **Important**: also update the `usdToCny` variable in the embedded JavaScript (used for computing struck-through original prices in the pricing section) and the footer text showing the rate.

### Adding a "Model Pricing" section

The dashboard can display current per-model unit prices (per 1M tokens) in a dedicated section. Steps:

1. **Backend**: Add a `pricing` key to the API response. Build it from the `PRICING` dict, deduplicating by `display_name`:
```python
pricing_export = []
seen = set()
for model_key, p in PRICING.items():
    display = p.get("display_name", model_key)
    if display in seen:
        continue
    seen.add(display)
    entry = {
        "model": display,
        "input_cache_hit": p["input_cache_hit"],
        "input_cache_miss": p["input_cache_miss"],
        "output": p["output"],
    }
    if p.get("discount"):
        entry["has_discount"] = True
        entry["discount_pct"] = p["discount_pct"]
        entry["discount_until"] = p.get("discount_until", "")
        entry["original_input_cache_hit"] = p.get("original_input_cache_hit")
        entry["original_input_cache_miss"] = p.get("original_input_cache_miss")
        entry["original_output"] = p.get("original_output")
    pricing_export.append(entry)
```

2. **Frontend HTML**: Add a new section block between the models section and footer:
```html
<div class="section">
    <h2>💰 模型单价 (每百万 Token · 人民币)</h2>
    <div id="pricing-table">
      <div class="loading">💰 加载中～</div>
    </div>
    <div style="font-size:12px;color:var(--text-muted);margin-top:12px;line-height:1.6">
      汇率 ¥7.25/USD · 定价来源: <a href="..." target="_blank" style="color:var(--accent3)">DeepSeek 官方</a>
    </div>
</div>
```

3. **Frontend JS**: In `render()`, after rendering the models table, render the pricing section:
```javascript
const pricing = data.pricing || [];
const pricingHTML = `<table class="models-table">...</table>`;
document.getElementById('pricing-table').innerHTML = pricingHTML;
```

4. **CNY as primary unit**: In the pricing table cells, display CNY as the main bold number with USD as secondary reference text. For cleaner display, provide user-friendly rounded CNY values rather than exact conversions — add a `price_cny` dict to the API response:

```python
CNY_DISPLAY = {
    "deepseek-v4-flash": {"input_cache_hit": 0.02, "input_cache_miss": 1, "output": 2},
    "deepseek-v4-pro": {"input_cache_hit": 0.025, "input_cache_miss": 3, "output": 6},
    "mimo-v2.5-pro": {"input_cache_hit": 1.40, "input_cache_miss": 7, "output": 21},
    "mimo-v2.5": {"input_cache_hit": 0.56, "input_cache_miss": 2.80, "output": 14},
    "mimo-v2-flash": {"input_cache_hit": 0.07, "input_cache_miss": 0.70, "output": 2.10},
}
```

Include this in each pricing entry:
```python
entry = {
    ...
    "price_cny": CNY_DISPLAY.get(display, {}),
}
```

Then in the frontend, use `p.price_cny` for primary display and `p.input_cache_hit` etc. for the USD reference:

```javascript
const cny = p.price_cny || {};
const hitCell = `<strong>¥${cny.input_cache_hit}</strong><br>
  <span style="font-size:11px;color:var(--text-muted)">≈ $${p.input_cache_hit}</span>`;
```

For discounted models, show the current discounted price in green with struck-through original (both in CNY):
```javascript
const cnyHit = (p.input_cache_hit * usdToCny).toFixed(4);
const hitCell = `<strong>¥${cnyHit}</strong><br><span style="font-size:11px;color:var(--text-muted)">≈ $${p.input_cache_hit}</span>`;
```
For discounted models, show current green price + struck-through original, both in CNY + USD reference.

### Pricing values

DeepSeek uses legacy model names (`deepseek-chat`, `deepseek-reasoner`) for V4 Flash. The panel should display the canonical V-series name instead. In `PRICING`, add a `display_name` field for legacy aliases:

**⚠️ Critical warning: `deepseek-4-flash` vs `deepseek-v4-flash`**

Do NOT confuse `deepseek-4-flash` with `deepseek-v4-flash`. Hermes' model normalizer (`hermes_cli/model_normalize.py`) maps:

| Config value | Normalized to | Result |
|---|---|---|
| `deepseek-v4-flash` | `deepseek-v4-flash` ✅ | V4 Flash with thinking mode |
| `deepseek-4-flash` | `deepseek-chat` ❌ | Legacy V3, **no thinking mode** |

The bare `deepseek-4-flash` (missing the `v`) does NOT match the V-series regex `^deepseek-v\d+([-.].+)?$` and falls through to the default → `deepseek-chat`. This means **thinking mode is silently disabled** and the model may behave differently. Always use `deepseek-v4-flash` in config.yaml.

To verify the mapping:
```bash
python3 -c "
import sys; sys.path.insert(0, '/usr/local/lib/hermes-agent')
from hermes_cli.model_normalize import normalize_model_for_provider
print('deepseek-4-flash  →', normalize_model_for_provider('deepseek-4-flash', 'deepseek'))
print('deepseek-v4-flash →', normalize_model_for_provider('deepseek-v4-flash', 'deepseek'))
"
```

```python
PRICING = {
    "deepseek-chat": {
        "input_cache_hit": 0.0028,
        "input_cache_miss": 0.14,
        "output": 0.28,
        "display_name": "deepseek-v4-flash",  # Show as modern name
    },
    ...
}
```

Then in the frontend JS, use `s.model_display || s.model` (served from the API) to render in the session table.

To merge legacy model names into the canonical model in the model-breakdown table, use a `CASE` expression in the SQL:

```sql
SELECT
    CASE
        WHEN model IN ('deepseek-chat', 'deepseek-reasoner') THEN 'deepseek-v4-flash'
        ELSE model
    END as display_model,
    COUNT(*) as sessions,
    ...
FROM sessions
GROUP BY display_model
```

And in the Python loop, rename the column:
```python
m["model"] = m.get("display_model", "")
```

### Pricing values

```python
PRICING = {
    "deepseek-v4-flash": {
        "input_cache_hit": 0.0028,
        "input_cache_miss": 0.14,
        "output": 0.28,
    },
    "deepseek-v4-pro": {
        "input_cache_hit": 0.003625,
        "input_cache_miss": 0.435,    # 75% off until 2026-05-31
        "output": 0.87,
        "discount": True,
        "discount_pct": 75,
    },
    # Xiaomi MiMo (overseas USD, input ≤ 256K)
    # Source: https://platform.xiaomimimo.com/docs/en-US/pricing
    "mimo-v2.5-pro": {
        "input_cache_hit": 0.20,
        "input_cache_miss": 1.00,
        "output": 3.00,
        "vendor": "Xiaomi",
    },
    "mimo-v2.5": {
        "input_cache_hit": 0.08,
        "input_cache_miss": 0.40,
        "output": 2.00,
        "vendor": "Xiaomi",
    },
    "mimo-v2-flash": {
        "input_cache_hit": 0.01,
        "input_cache_miss": 0.10,
        "output": 0.30,
        "vendor": "Xiaomi",
    },
}
```

### Adding a new vendor's models

When switching primary models or adding a new provider, follow this checklist:

1. **Get official pricing** from the provider's docs page. Use `browser_navigate` + `browser_console` to scrape if needed.
2. **Add entries to `PRICING`** dict with `"vendor"` tag (e.g. `"vendor": "Xiaomi"`).
3. **Add model name aliases** — if DB has variant names (e.g. `xiaomi/mimo-v2.5`), add them with `"display_name"` pointing to canonical.
4. **Update `calc_cost()` normalization** — add `elif` branches for new model name variants.
5. **Update `CNY_DISPLAY`** dict with user-friendly rounded CNY values per million tokens.
6. **Update SQL `CASE WHEN`** in both aggregate queries (total cost + model breakdown) to normalize new aliases.
7. **Update `pricing_export`** to include `"vendor"` field.
8. **Update frontend** — vendor tags in pricing table and model table, footer text, subtitle.
9. **Note large-context pricing** in the pricing section description if applicable (e.g. MiMo 256K-1M = 2× base price).
10. **Restart**: `systemctl restart hermes-token-monitor`

### Current pricing summary (as of 2026-05)

| Model | Cache Hit | Cache Miss | Output | Vendor | Notes |
|---|---|---|---|---|---|
| deepseek-v4-flash | $0.0028 | $0.14 | $0.28 | DeepSeek | |
| deepseek-v4-pro | $0.003625 | $0.435 | $0.87 | DeepSeek | 75% off → 2026-05-31 |
| mimo-v2.5-pro | $0.20 | $1.00 | $3.00 | Xiaomi | 256K-1M = 2× |
| mimo-v2.5 | $0.08 | $0.40 | $2.00 | Xiaomi | 256K-1M = 2× |
| mimo-v2-flash | $0.01 | $0.10 | $0.30 | Xiaomi | ≤256K only |

MiMo domestic CNY display values: v2.5-pro ¥1.40/¥7/¥21, v2.5 ¥0.56/¥2.80/¥14, v2-flash ¥0.07/¥0.70/¥2.10.

Full MiMo pricing reference (domestic/overseas, credit ratios, 100T plan): `references/xiaomi-mimo-pricing.md`

Add new models by appending entries to `PRICING` (and `CNY_DISPLAY` for rounded CNY). Restart the service after changes:
```bash
sudo systemctl restart hermes-token-monitor
```

### MiMo model name normalization

DB may contain variant names from different API paths. Normalize in `calc_cost()`, SQL CASE, and pricing export:

| DB raw name | Normalized to | Notes |
|---|---|---|
| `mimo-v2.5-pro` | `mimo-v2.5-pro` | canonical |
| `mimo-v2-pro` | `mimo-v2.5-pro` | alias |
| `xiaomi/mimo-v2.5` | `mimo-v2.5` | strip vendor prefix |
| `mimo-v2.5` | `mimo-v2.5` | canonical |

Add to SQL CASE in both aggregate queries:
```sql
WHEN model IN ('mimo-v2-pro') THEN 'mimo-v2.5-pro'
WHEN model IN ('xiaomi/mimo-v2.5') THEN 'mimo-v2.5'
```

### Xiaomi Token Plan: credits ≠ tokens

Xiaomi's Token Plan uses a **credit** system, not raw tokens. Key conversion rates (from [official docs](https://platform.xiaomimimo.com/docs/en-US/tokenplan/subscription)):

| Model | Credit ratio |
|---|---|
| MiMo-V2.5-Pro / V2-Pro | **2×** (1 token = 2 credits) |
| MiMo-V2.5 / V2-Omni | 1× (1 token = 1 credit) |
| TTS series | 0× (limited-time free) |

When comparing panel data to Xiaomi console's "积分" (credits), apply these ratios. If panel shows X tokens for Pro model, multiply by 2 for credits. Remaining discrepancy likely from: (a) `cache_write_tokens` not recorded in state.db (always 0), (b) subagent API calls not logged to state.db.

### MiMo two-tier context pricing

MiMo models have different pricing for input ≤256K vs 256K-1M context:

| Model | ≤256K (hit/miss/out) | 256K-1M (hit/miss/out) |
|---|---|---|
| mimo-v2.5-pro (CNY) | ¥1.40/¥7/¥21 | ¥2.80/¥14/¥42 |
| mimo-v2.5 (CNY) | ¥0.56/¥2.80/¥14 | ¥1.12/¥5.60/¥28 |
| mimo-v2-flash | ≤256K only | N/A |

Note this in the pricing section description. The panel uses ≤256K pricing by default.

## Troubleshooting

- **401 on external access**: nginx `auth_basic` is inherited from the parent server block. Add `auth_basic off;` inside the `/token/` location, then `systemctl restart nginx` (reload is not enough).
- **502 Bad Gateway**: Token monitor service is down. Check `systemctl status hermes-token-monitor`.
- **Cost showing $0**: Model not in `PRICING` dict. Add pricing entry and restart.
- **No sessions showing**: `state.db` may be empty or at a different path. Check `DB_PATH` in server.py.
- **Port conflict**: Change `PORT` in server.py and update nginx proxy_pass accordingly.

## Debugging Pricing Discrepancies

If the dashboard cost doesn't match what the provider (e.g., DeepSeek Platform) shows, use this systematic diagnostic approach.

### 0. Establish the unit of comparison first

**The most common cause of "mismatch" is comparing different units or timeframes.** Before anything else, ask the user:

- **Currency**: Is the provider showing USD or RMB/CNY? The panel has historically shown USD; if the user is looking at RMB on the provider's page, apply the exchange rate (~7.25).
- **Timeframe**: Is the user looking at "total spend since account creation" vs "today's spend only"? The panel only has **data from state.db**, which may only contain recent sessions.
- **Token accounting**: How does the provider count "total tokens"? Common definitions:
  - `total = cache_hit_input + cache_miss_input + output` (most comprehensive)
  - `total = cache_miss_input + output` (billable-only)
  - `total = cache_hit_input + cache_miss_input` (input-only)
  The panel's DB uses `input_tokens` = cache_miss only, `cache_read_tokens` = cache_hit, `output_tokens` = output.

### 1. Understand the DB field semantics

The `state.db` `sessions` table columns:
- **`input_tokens`** — only **cache_miss** tokens (tokens that were NOT found in the context cache)
- **`cache_read_tokens`** — tokens served from context cache hit
- **`output_tokens`** — completion tokens generated
- **`actual_cost_usd`** — **always `NULL`** in Hermes Agent. The agent does NOT persist the provider's actual billing amount. Only `estimated_cost_usd` may be populated (also often 0).
- The panel recalculates costs independently using the PRICING dict → it can only ever be an *estimate*, never exact.

So the panel's calculation is:
```python
cost = cache_read/1M * input_cache_hit_price  +  input_tokens/1M * input_cache_miss_price  +  output_tokens/1M * output_price
```
```

### 2. Check data coverage by session count

`state.db` only contains sessions since Hermes Agent started or since the last DB prune. Check coverage:

```sql
-- Date range of sessions in DB
SELECT MIN(date(started_at, 'unixepoch')), MAX(date(started_at, 'unixepoch')) FROM sessions;

-- Partition by model to see what's recorded
SELECT model, 
       COUNT(*) as sessions,
       SUM(input_tokens) as total_cache_miss,
       SUM(output_tokens) as total_output,
       SUM(cache_read_tokens) as total_cache_hit,
       SUM(input_tokens) + SUM(output_tokens) + SUM(cache_read_tokens) as total_all_tokens
FROM sessions GROUP BY model;
```

**Key insight**: Compare the panel's total token count per model against what the provider shows. If the provider shows 20M flash tokens and the panel only has 2M, the DB is missing sessions. Possible causes:
- **DB was recently pruned or newly started** — check retention settings: `sessions.retention_days` in config.yaml (default 90)
- **Sessions from other channels** (e.g., CLI, webhook, cronjob) might not be logged yet
- **WAL file not checkpointed** — SQLite WAL mode means some data may be in `state.db-wal` but not yet in the main `state.db` file. Check WAL file size:
  ```bash
  ls -la ~/.hermes/state.db-wal  # If large (>1MB), might have unmerged data
  ```
  Force a checkpoint to merge WAL into main DB:
  ```python
  conn = sqlite3.connect('/root/.hermes/state.db')
  conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
  conn.close()
  ```

### 3. Run a diagnostic with cost breakdown by model

Use this comprehensive diagnostic script:

```bash
python3 << 'PYEOF'
import sqlite3
from datetime import datetime

conn = sqlite3.connect('/root/.hermes/state.db')
cur = conn.cursor()

# Pricing (update from https://api-docs.deepseek.com/quick_start/pricing)
PRICING = {
    'deepseek-v4-flash': {'hit': 0.0028, 'miss': 0.14, 'out': 0.28},
    'deepseek-v4-pro': {'hit': 0.003625, 'miss': 0.435, 'out': 0.87},
    'deepseek-chat': {'hit': 0.0028, 'miss': 0.14, 'out': 0.28},
    'deepseek-reasoner': {'hit': 0.0028, 'miss': 0.14, 'out': 0.28},
}
USD_TO_CNY = 7.25

# Per-session detail
cur.execute("""
    SELECT id, model, input_tokens, output_tokens, cache_read_tokens, 
           estimated_cost_usd, actual_cost_usd, started_at,
           message_count, tool_call_count
    FROM sessions ORDER BY started_at
""")
rows = cur.fetchall()

print(f"{'Session ID':<30} {'Model':<18} {'CacheMiss':>10} {'Output':>8} {'CacheHit':>10} {'Msgs':>5} {'Cost(USD)':>10}")
print("=" * 95)
for r in rows:
    sid, model, inp, out, cache, est, act, ts, msgs, tools = r
    dt = datetime.fromtimestamp(ts).strftime('%H:%M') if ts else '--'
    inp = inp or 0; out = out or 0; cache = cache or 0
    p = PRICING.get(model, {'hit': 0, 'miss': 0, 'out': 0})
    cost = cache/1e6*p['hit'] + inp/1e6*p['miss'] + out/1e6*p['out']
    print(f"{sid[:28]:<30} {model:<18} {inp:>10,} {out:>8,} {cache:>10,} {msgs or 0:>5} ${cost:<8.6f}")

print("=" * 95)

# Model summary with costs
cur.execute("""
    SELECT model, COUNT(*), SUM(input_tokens), SUM(output_tokens), SUM(cache_read_tokens)
    FROM sessions GROUP BY model ORDER BY SUM(input_tokens)+SUM(output_tokens)+SUM(cache_read_tokens) DESC
""")
total_cny = 0
for r in cur.fetchall():
    model, cnt, inp, out, cache = r
    inp = inp or 0; out = out or 0; cache = cache or 0
    p = PRICING.get(model, {'hit': 0, 'miss': 0, 'out': 0})
    cost = cache/1e6*p['hit'] + inp/1e6*p['miss'] + out/1e6*p['out']
    cost_cny = cost * USD_TO_CNY
    total_cny += cost_cny
    all_tokens = inp + out + cache
    print(f"\n{model}:")
    print(f"  Sessions: {cnt}")
    print(f"  Total tokens (all): {all_tokens:,}")
    print(f"    CacheHit: {cache:,}  CacheMiss(input): {inp:,}  Output: {out:,}")
    print(f"    Cost: ${cost:.4f} = ¥{cost_cny:.4f}")

print(f"\n{'='*45}")
print(f"Panel total: ¥{total_cny:.4f} (≈ ${total_cny/USD_TO_CNY:.4f})")
print(f"DeepSeek RMB: ¥__ASK_USER__")
conn.close()
PYEOF
```

### 4. Verify pricing is current

Pull the latest pricing from [DeepSeek API Docs](https://api-docs.deepseek.com/quick_start/pricing) by scraping the HTML table:
```bash
curl -s https://api-docs.deepseek.com/quick_start/pricing | grep -oP '\\$[0-9.]+' | head -6
```
Then cross-reference each value in `PRICING`. Common mismatches:
- `deepseek-v4-pro` has a 75% discount until 2026-05-31 → `$0.003625` / `$0.435` / `$0.87`
- `deepseek-chat` and `deepseek-reasoner` are legacy aliases for `deepseek-v4-flash` → same pricing (`$0.0028` / `$0.14` / `$0.28`)
- On 2026/4/26, the cache hit price was reduced to 1/10 of launch price across all models

## Data Integrity: Avoiding Silent Mismatches

A key class of bugs discovered during maintenance is **silent data inconsistency** — where different parts of the dashboard use different data scopes and produce numbers that don't add up. Here are the patterns to watch for:

### Pattern 1: Summary from ALL rows vs session list from LIMIT N

If the summary stats (total tokens, total sessions) come from `SELECT SUM(...) FROM sessions` and the session table display uses `SELECT ... LIMIT 500`, the **total cost** calculated by summing per-session costs will only cover the last 500 sessions, while the **total tokens** includes all sessions. They disagree.

**Fix**: Calculate total cost from a **separate SQL aggregate query** that runs over all sessions, not by summing per-session costs:

```python
# ❌ Wrong — total cost only covers 500 sessions
total_calculated_cost_cny = 0.0
for s in sessions_raw[:500]:  # LIMIT 500
    total_calculated_cost_cny += calc_cost(s)[\"cost_cny\"]
summary[\"total_cost_cny\"] = total_calculated_cost_cny

# ✅ Correct — aggregate over ALL sessions
cur.execute(\"\"\"
    SELECT model, SUM(input_tokens), SUM(output_tokens), SUM(cache_read_tokens)
    FROM sessions GROUP BY model
\"\"\")
all_cost_cny = 0.0
for row in cur.fetchall():
    ci = calc_cost(row[\"model\"], row[\"input_tokens\"], row[\"output_tokens\"], row[\"cache_read_tokens\"])
    all_cost_cny += ci[\"cost_cny\"]
summary[\"total_cost_cny\"] = round(all_cost_cny, 6)
```

### Pattern 2: Unknown model → ¥0 (silent data loss)

When `PRICING.get(model, DEFAULT_PRICING)` returns all-zeros for an unknown model, the session silently shows ¥0 cost. The user sees no red flag — it just looks free.

**Fix**: Use a reasonable fallback pricing instead of zeros:

```python
UNKNOWN_MODEL_PRICING = {
    \"input_cache_hit\": 0.0028,    # deepseek-v4-flash rate as default
    \"input_cache_miss\": 0.14,
    \"output\": 0.28,
}

def calc_cost(model, input_tokens, output_tokens, cache_read_tokens=0):
    # Normalize first
    normalized = model
    if model in (\"deepseek-chat\", \"deepseek-reasoner\"):
        normalized = \"deepseek-v4-flash\"
    p = PRICING.get(normalized, UNKNOWN_MODEL_PRICING)  # Never zero
```

### Pattern 3: calc_cost() must normalize model names

If the DB has legacy model names like `deepseek-chat` or `deepseek-reasoner`, they won't match PRICING keys (`deepseek-v4-flash`). Even if the SQL model-breakdown query normalizes them via `CASE WHEN`, the per-session loop passes the raw model name to `calc_cost()`.

**Fix**: Normalize inside `calc_cost()` itself, not just in the SQL, so every call path is covered.

### Pattern 4: \"total tokens\" must include cache_read_tokens

In Hermes Agent's `state.db`:
- `input_tokens` = **cache_miss** tokens only (tokens NOT found in context cache)
- `cache_read_tokens` = **cache_hit** tokens (served from cache)
- `output_tokens` = completion tokens

If you compute `total_tokens = input + output`, you miss the cache hits. The cache hit count is often much larger than the miss count (typical hit rates are 95%+), so this makes \"total tokens\" appear much smaller than it should be compared to the \"cache hit\" column.

**Fix**: Always include all three:
```sql
COALESCE(SUM(input_tokens), 0) + COALESCE(SUM(output_tokens), 0) + COALESCE(SUM(cache_read_tokens), 0) as total_tokens
```

This applies everywhere: summary stats, model breakdown, and frontend display.

### Pattern 5: Exchange rate staleness

Hardcoded exchange rates silently drift. One session quoted ¥7.25/USD when the live rate was ¥6.85 — a ~6% overestimate on all CNY figures.

**Fix**: Check the rate at deployment time and periodically:
```bash
curl -s \"https://open.er-api.com/v6/latest/USD\" | python3 -c \"import sys,json; print(json.load(sys.stdin)['rates'].get('CNY'))\"
```

Search for ALL occurrences of the old rate in the file (Python constant AND JavaScript template strings) and update them:

```bash
grep -n '7.25\|6.85\|<your-old-rate>' server.py
```

## Common Pitfalls Summary

- **Total cost scope != total token scope** → mismatch when sessions exceed LIMIT
- **calc_cost() before model normalization** → ¥0 for legacy model names
- **ZERO default pricing** → ¥0 for unknown models, silently hiding costs
- **total_tokens = input + output** → cache hits excluded
- **Exchange rate hardcoded in one place only** → some values stay stale
- **auth_basic off needs restart, not reload** → documented in parent skill

### 5. If cost still doesn't match: cross-check token accounting formulas

Sometimes the provider's "total tokens" in the dashboard means something different from what Hermes logs. Try these alternative formulas:

```python
# Provider sees 20M flash tokens — what does that include?
# Formula A: cache_hit + cache_miss + output  (everything)
# Formula B: cache_miss + output  (billable-only, cache_hit is discounted)
# Formula C: cache_hit + cache_miss  (input-only)

# If user says "flash total = 20,457,395" but panel has:
#   cache_hit=1,874,816  cache_miss=106,299  output=22,235
#   sum all = 2,003,350 → way less than 20M → missing sessions

# The discrepancy in token count (e.g. 20M vs 2M for flash) 
# ALWAYS means sessions are missing from state.db, not a pricing formula issue.
```

### 6. Known limitations

- **No cross-session persistence**: the panel shows data from today onward only; it won't match the DeepSeek platform's "total spend" from account creation.
- **No `actual_cost_usd`**: the real billing amount returned by DeepSeek in the API response is **not stored** in the DB. The panel can only estimate.
- **Token counts may differ**: the API response token counts and the counts Hermes logs could diverge due to system messages or prompt formatting that Hermes strips before logging.
- **汇率差异**: If comparing the panel (CNY) to the provider's USD pricing, apply the current exchange rate (~6.85).
- **Session pruning**: `sessions.auto_prune` in config.yaml controls whether old sessions get deleted. Default is `false` but check if it changed.
- **Fresh DB**: On first run or after a DB reset, `state.db` starts empty. Only sessions created after that point are recorded.
- **Multi-vendor frontend**: Use vendor tags (colored badges) in pricing and model tables. Example: orange `Xiaomi` tag vs green `DeepSeek` tag. Add `"vendor"` field to PRICING entries and pass through API to frontend.
- **Multi-channel**: If Hermes operates via CLI AND DingTalk AND cronjobs, make sure to check all channels' sessions are present in the DB.
