#!/usr/bin/env python3
"""
Token Usage Monitor — Real-time dashboard for AI token consumption and costs.
Reads from a SQLite database (state.db) or generates simulated data.
Serves an auto-refreshing HTML page on http://localhost:8080.
Uses only Python stdlib: http.server, sqlite3, json. No external deps.
"""

import http.server
import json
import os
import random
import sqlite3
from datetime import datetime, timedelta

# ── Configuration ──────────────────────────────────────────────────────────

DB_PATH = os.environ.get("TOKEN_MONITOR_DB", "state.db")
PORT = int(os.environ.get("TOKEN_MONITOR_PORT", 8080))
REFRESH_SECONDS = 10
SIMULATE = os.environ.get("TOKEN_MONITOR_SIMULATE", "1") == "1"  # default: simulate if no real DB

# Pricing per 1K tokens (in ¥)
PRICING = {
    "mimo-v2.5-pro":     {"provider": "xiaomi",  "input": 0.001, "output": 0.005},
    "deepseek-v4-pro":   {"provider": "deepseek","input": 0.002, "output": 0.008},
    "deepseek-v4-flash": {"provider": "deepseek","input": 0.0005,"output": 0.002},
}

# ── Database ────────────────────────────────────────────────────────────────

def init_db():
    """Create or migrate the messages table. Returns an open connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT,
            role         TEXT,
            content      TEXT,
            model        TEXT,
            provider     TEXT,
            tokens_in    INTEGER DEFAULT 0,
            tokens_out   INTEGER DEFAULT 0,
            timestamp    TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_model ON messages(model)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)")
    conn.commit()
    return conn


def seed_simulated_data(conn, hours=72):
    """Populate the database with realistic-looking synthetic data."""
    # Check if we already have data
    cur = conn.execute("SELECT COUNT(*) FROM messages")
    count = cur.fetchone()[0]
    if count > 0:
        return  # already populated

    models = list(PRICING.keys())
    roles = ["user", "assistant", "system", "tool"]
    sessions = [f"sess-{i:04x}" for i in range(1, 8)]

    now = datetime.utcnow()
    rows = []

    for i in range(500):
        ts = now - timedelta(
            hours=random.uniform(0, hours),
            minutes=random.uniform(0, 59),
            seconds=random.uniform(0, 59),
        )
        model = random.choices(models, weights=[0.25, 0.45, 0.30])[0]
        provider = PRICING[model]["provider"]
        role = "assistant" if random.random() < 0.55 else random.choice(roles)
        tokens_in = random.randint(80, 8000)
        tokens_out = random.randint(40, 6000)
        session_id = random.choice(sessions)

        rows.append((
            session_id, role,
            f"[Simulated] {role} message for {model}",
            model, provider, tokens_in, tokens_out,
            ts.strftime("%Y-%m-%d %H:%M:%S"),
        ))

    conn.executemany(
        "INSERT INTO messages(session_id, role, content, model, provider, tokens_in, tokens_out, timestamp) "
        "VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    print(f"[token_monitor] Seeded {len(rows)} simulated messages into {DB_PATH}")


def query_stats(conn):
    """Query aggregated token/cost stats from the database."""
    cur = conn.execute("""
        SELECT
            model,
            provider,
            SUM(tokens_in)  AS total_in,
            SUM(tokens_out) AS total_out,
            COUNT(*)        AS calls
        FROM messages
        GROUP BY model, provider
        ORDER BY provider, model
    """)
    rows = cur.fetchall()

    models_stats = []
    provider_totals = {}  # provider -> {"calls": N, "cost": ¥}
    grand_cost = 0.0

    for r in rows:
        model = r["model"]
        provider = r["provider"]
        tokens_in = r["total_in"] or 0
        tokens_out = r["total_out"] or 0
        calls = r["calls"] or 0

        price = PRICING.get(model, {"input": 0, "output": 0, "provider": provider})
        cost_in = (tokens_in / 1000) * price["input"]
        cost_out = (tokens_out / 1000) * price["output"]
        cost_total = cost_in + cost_out

        models_stats.append({
            "model": model,
            "provider": provider,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "calls": calls,
            "cost_in": round(cost_in, 4),
            "cost_out": round(cost_out, 4),
            "cost_total": round(cost_total, 4),
        })

        if provider not in provider_totals:
            provider_totals[provider] = {"calls": 0, "cost": 0.0}
        provider_totals[provider]["calls"] += calls
        provider_totals[provider]["cost"] += cost_total
        grand_cost += cost_total

    # Recent activity (last 24h)
    cur = conn.execute("""
        SELECT
            model,
            provider,
            SUM(tokens_in)  AS total_in,
            SUM(tokens_out) AS total_out,
            COUNT(*)        AS calls
        FROM messages
        WHERE timestamp >= datetime('now', '-24 hours')
        GROUP BY model, provider
        ORDER BY provider, model
    """)
    recent_rows = cur.fetchall()

    recent_models = []
    for r in recent_rows:
        model = r["model"]
        provider = r["provider"]
        price = PRICING.get(model, {"input": 0, "output": 0, "provider": provider})
        cost_total = ((r["total_in"] or 0) / 1000) * price["input"] + \
                     ((r["total_out"] or 0) / 1000) * price["output"]
        recent_models.append({
            "model": model,
            "provider": provider,
            "tokens_in": r["total_in"] or 0,
            "tokens_out": r["total_out"] or 0,
            "calls": r["calls"] or 0,
            "cost_total": round(cost_total, 4),
        })

    return {
        "models": models_stats,
        "providers": {k: {"name": k, "calls": v["calls"], "cost": round(v["cost"], 4)}
                      for k, v in provider_totals.items()},
        "grand_cost": round(grand_cost, 4),
        "total_models": len(models_stats),
        "recent_24h": recent_models,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


# ── HTML Rendering ──────────────────────────────────────────────────────────

CSS = """
:root {
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --orange: #d29922;
    --purple: #a371f7;
    --red: #f85149;
    --deepseek: #58a6ff;
    --xiaomi: #ff6a00;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.6;
    min-height: 100vh;
}
header {
    background: var(--card); border-bottom: 1px solid var(--border);
    padding: 20px 32px; display:flex; justify-content:space-between; align-items:center;
    position: sticky; top:0; z-index:10;
}
header h1 { font-size: 1.5rem; font-weight: 600; }
header h1 span { color: var(--accent); }
header .badge {
    font-size: 0.8rem; padding: 4px 12px; border-radius: 20px;
    background: rgba(88,166,255,0.12); color: var(--accent);
    border: 1px solid rgba(88,166,255,0.3);
}
.container { max-width: 1100px; margin: 0 auto; padding: 28px 32px; }

/* Cards */
.cards { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:16px; margin-bottom:28px; }
.card {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; transition: transform 0.15s, box-shadow 0.15s;
}
.card:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.3); }
.card .label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom:6px; }
.card .value { font-size: 1.8rem; font-weight: 700; }
.card .sub { font-size: 0.8rem; color: var(--muted); margin-top: 4px; }
.card.xiaomi  .value { color: var(--xiaomi); }
.card.deepseek .value { color: var(--deepseek); }
.card.accent .value { color: var(--accent); }

/* Section headings */
h2 {
    font-size: 1.15rem; font-weight: 600; margin-bottom: 16px;
    display: flex; align-items: center; gap: 8px;
}
h2::after { content:''; flex:1; height:1px; background: var(--border); }

/* Model table */
.table-wrap { overflow-x: auto; margin-bottom: 28px; }
table {
    width: 100%; border-collapse: collapse; font-size: 0.9rem;
    background: var(--card); border-radius: 12px; overflow: hidden;
    border: 1px solid var(--border);
}
th, td { padding: 12px 16px; text-align: left; white-space: nowrap; }
th { background: rgba(48,54,61,0.6); color: var(--muted); font-weight: 500; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
td { border-top: 1px solid var(--border); }
tr:hover td { background: rgba(88,166,255,0.04); }
.provider-tag {
    display: inline-block; font-size: 0.7rem; padding: 2px 8px; border-radius: 4px;
    font-weight: 500; text-transform: uppercase; letter-spacing: 0.03em;
}
.provider-tag.deepseek { background: rgba(88,166,255,0.15); color: var(--deepseek); }
.provider-tag.xiaomi   { background: rgba(255,106,0,0.15);  color: var(--xiaomi); }
.num { font-variant-numeric: tabular-nums; text-align: right; }

/* Bar charts */
.bar-cell { min-width: 180px; }
.bar-row { display:flex; align-items:center; gap:8px; margin: 3px 0; }
.bar-row .bar-label { font-size:0.7rem; color:var(--muted); width:50px; text-align:right; flex-shrink:0; }
.bar-bg { flex:1; height:10px; border-radius:5px; background: rgba(48,54,61,0.6); overflow:hidden; }
.bar-fill { height:100%; border-radius:5px; transition: width 0.5s ease; }
.bar-fill.in  { background: linear-gradient(90deg, #58a6ff, #79c0ff); }
.bar-fill.out { background: linear-gradient(90deg, #a371f7, #c2a0fa); }
.bar-row .bar-val { font-size:0.7rem; color:var(--text); width:55px; text-align:left; flex-shrink:0; }

/* Cost breakdown bars */
.cost-bar { margin-bottom: 12px; }
.cost-bar .cost-label { display:flex; justify-content:space-between; margin-bottom: 4px; font-size: 0.85rem; }
.cost-bar .cost-bg { height: 20px; border-radius: 6px; background: rgba(48,54,61,0.6); overflow: hidden; display: flex; }
.cost-bar .cost-fill {
    height: 100%; border-radius: 6px; display: flex; align-items: center;
    justify-content: center; font-size: 0.7rem; font-weight: 600; color: #fff;
    transition: width 0.5s ease; min-width: 2px;
}
.cost-fill.xiaomi  { background: linear-gradient(90deg, #d24900, #ff6a00); }
.cost-fill.deepseek { background: linear-gradient(90deg, #1f6feb, #58a6ff); }

/* Recent activity mini-bars */
.recent-row { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--border); font-size:0.82rem; }
.recent-row:last-child { border-bottom:none; }
.recent-row .r-model { flex:1; min-width:130px; }
.recent-row .r-tokens { color: var(--muted); font-size:0.75rem; margin-right:8px; }
.recent-row .r-cost { font-weight:600; min-width:70px; text-align:right; }
.recent-row .mini-bar { flex:1; height:6px; border-radius:3px; background:rgba(48,54,61,0.6); overflow:hidden; }
.recent-row .mini-fill { height:100%; border-radius:3px; }
.mini-fill.deepseek { background: var(--deepseek); }
.mini-fill.xiaomi   { background: var(--xiaomi); }

footer {
    text-align: center; color: var(--muted); font-size: 0.75rem;
    padding: 24px 32px; border-top: 1px solid var(--border); margin-top: 20px;
}
footer .dot { display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--green); margin-right:6px; animation:pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
"""


def fmt_tokens(n):
    """Human-readable token count."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def fmt_cost(n):
    """Format cost in ¥ with appropriate precision."""
    if abs(n) < 0.01:
        return f"¥{n:.4f}"
    return f"¥{n:.2f}"


def render_bar_chart(tokens_in, tokens_out, max_val):
    """Render an inline bar chart row for a model (CSS bars)."""
    ratio_in = (tokens_in / max_val * 100) if max_val > 0 else 0
    ratio_out = (tokens_out / max_val * 100) if max_val > 0 else 0
    return f"""
    <div class="bar-cell">
      <div class="bar-row">
        <span class="bar-label">In</span>
        <div class="bar-bg"><div class="bar-fill in" style="width:{ratio_in:.1f}%"></div></div>
        <span class="bar-val">{fmt_tokens(tokens_in)}</span>
      </div>
      <div class="bar-row">
        <span class="bar-label">Out</span>
        <div class="bar-bg"><div class="bar-fill out" style="width:{ratio_out:.1f}%"></div></div>
        <span class="bar-val">{fmt_tokens(tokens_out)}</span>
      </div>
    </div>"""


def build_html(stats):
    """Assemble the full HTML dashboard."""
    models = stats["models"]
    providers = stats["providers"]
    recent = stats["recent_24h"]
    grand_cost = stats["grand_cost"]
    ts = stats["timestamp"]

    # Find max token count for scaling bars
    all_tokens = [m["tokens_in"] + m["tokens_out"] for m in models]
    max_tok = max(all_tokens) if all_tokens else 1

    # Find max cost for scaling provider bars
    provider_costs = [p["cost"] for p in providers.values()]
    max_pcost = max(provider_costs) if provider_costs else 1

    # Find max recent cost for mini bars
    max_rcost = max((r["cost_total"] for r in recent), default=1)

    # Build model table rows
    model_rows = []
    for m in models:
        model_rows.append(f"""
        <tr>
          <td><strong>{m["model"]}</strong></td>
          <td><span class="provider-tag {m['provider']}">{m["provider"]}</span></td>
          <td class="num">{m["calls"]}</td>
          <td>{render_bar_chart(m["tokens_in"], m["tokens_out"], max_tok)}</td>
          <td class="num" style="color:var(--accent)">{fmt_cost(m["cost_total"])}</td>
        </tr>""")

    # Build provider cost bars
    cost_bars = []
    for _, p in providers.items():
        pct = (p["cost"] / max_pcost * 100) if max_pcost > 0 else 0
        cost_bars.append(f"""
        <div class="cost-bar">
          <div class="cost-label">
            <span><span class="provider-tag {p['name']}" style="font-size:0.75rem">{p['name']}</span> {p['calls']} calls</span>
            <strong>{fmt_cost(p['cost'])}</strong>
          </div>
          <div class="cost-bg">
            <div class="cost-fill {p['name']}" style="width:{pct:.1f}%">{fmt_cost(p['cost'])}</div>
          </div>
        </div>""")

    # Recent 24h rows
    recent_rows = []
    for r in recent:
        rpct = (r["cost_total"] / max_rcost * 100) if max_rcost > 0 else 0
        recent_rows.append(f"""
        <div class="recent-row">
          <span class="r-model">{r["model"]}</span>
          <span class="r-tokens">{fmt_tokens(r["tokens_in"] + r["tokens_out"])} tokens</span>
          <div class="mini-bar">
            <div class="mini-fill {r['provider']}" style="width:{rpct:.1f}%"></div>
          </div>
          <span class="r-cost">{fmt_cost(r["cost_total"])}</span>
        </div>""")

    xiaomi_cost = providers.get("xiaomi", {}).get("cost", 0)
    deepseek_cost = providers.get("deepseek", {}).get("cost", 0)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="{REFRESH_SECONDS}">
  <title>Token Monitor — AI Usage Dashboard</title>
  <style>{CSS}</style>
</head>
<body>
<header>
  <h1>🔍 Token <span>Monitor</span></h1>
  <div class="badge">↻ {REFRESH_SECONDS}s refresh</div>
</header>

<div class="container">

  <!-- Summary cards -->
  <div class="cards">
    <div class="card deepseek">
      <div class="label">DeepSeek</div>
      <div class="value">{fmt_cost(deepseek_cost)}</div>
      <div class="sub">{providers.get("deepseek", {}).get("calls", 0)} calls</div>
    </div>
    <div class="card xiaomi">
      <div class="label">Xiaomi MiMo</div>
      <div class="value">{fmt_cost(xiaomi_cost)}</div>
      <div class="sub">{providers.get("xiaomi", {}).get("calls", 0)} calls</div>
    </div>
    <div class="card accent">
      <div class="label">Total Cost</div>
      <div class="value">{fmt_cost(grand_cost)}</div>
      <div class="sub">{stats["total_models"]} models tracked</div>
    </div>
  </div>

  <!-- Model breakdown -->
  <h2>📊 Per-Model Usage</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>Model</th><th>Provider</th><th>Calls</th><th>Tokens (In / Out)</th><th>Cost</th></tr>
      </thead>
      <tbody>
        {''.join(model_rows) if model_rows else '<tr><td colspan="5" style="color:var(--muted);text-align:center;padding:24px">No data yet</td></tr>'}
      </tbody>
    </table>
  </div>

  <!-- Cost breakdown -->
  <h2>💰 Cost by Provider</h2>
  <div style="background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:28px">
    {''.join(cost_bars) if cost_bars else '<p style="color:var(--muted)">No cost data</p>'}
  </div>

  <!-- Recent 24h -->
  <h2>🕐 Last 24 Hours</h2>
  <div style="background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin-bottom:28px">
    {''.join(recent_rows) if recent_rows else '<p style="color:var(--muted)">No recent activity</p>'}
  </div>

</div>

<footer>
  <span class="dot"></span> Token Monitor &middot; Updated {ts} &middot; Data source: {DB_PATH}
</footer>
</body>
</html>"""


# ── HTTP Server ─────────────────────────────────────────────────────────────

class TokenMonitorHandler(http.server.BaseHTTPRequestHandler):
    """Single-handler: / returns the dashboard, /api/stats returns JSON."""

    def log_message(self, fmt, *args):
        """Quiet logging – only show when verbose."""
        if os.environ.get("TOKEN_MONITOR_VERBOSE"):
            super().log_message(fmt, *args)

    def do_GET(self):
        path = self.path.rstrip("/") or "/"

        if path == "/" or path == "/index.html":
            self._serve_dashboard()
        elif path == "/api/stats":
            self._serve_api()
        elif path == "/health":
            self._serve_json({"status": "ok"})
        else:
            self.send_error(404)

    def _serve_dashboard(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            stats = query_stats(conn)
        finally:
            conn.close()
        html = build_html(stats)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _serve_api(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            stats = query_stats(conn)
        finally:
            conn.close()
        self._serve_json(stats)

    def _serve_json(self, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    # Ensure parent directory exists
    db_dir = os.path.dirname(os.path.abspath(DB_PATH)) or "."
    os.makedirs(db_dir, exist_ok=True)

    print(f"[token_monitor] Database: {DB_PATH}")
    print(f"[token_monitor] Port:     {PORT}")
    print(f"[token_monitor] Refresh:  {REFRESH_SECONDS}s")
    print(f"[token_monitor] Simulate: {SIMULATE}")

    # Initialize DB
    conn = init_db()
    if SIMULATE:
        seed_simulated_data(conn)
    conn.close()

    # Start server
    server = http.server.HTTPServer(("127.0.0.1", PORT), TokenMonitorHandler)
    print(f"[token_monitor] Dashboard → http://localhost:{PORT}")
    print(f"[token_monitor] API      → http://localhost:{PORT}/api/stats")
    print("[token_monitor] Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[token_monitor] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
