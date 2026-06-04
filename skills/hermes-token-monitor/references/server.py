#!/usr/bin/env python3
"""Token 监控服务 - 实时展示 Hermes Agent 的 Token 用量"""

import http.server
import json
import sqlite3
import os
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs

DB_PATH = os.path.expanduser("~/.hermes/state.db")
PORT = 8765
HOST = "127.0.0.1"  # 通过 nginx 代理，绑定本地即可

# DeepSeek 官方定价 - 每百万 Token (USD)，来源: https://api-docs.deepseek.com/quick_start/pricing
PRICING = {
    "deepseek-v4-flash": {
        "input_cache_hit": 0.0028,
        "input_cache_miss": 0.14,
        "output": 0.28,
    },
    "deepseek-v4-pro": {
        # 75% 折扣至 2026/05/31 15:59 UTC
        "input_cache_hit": 0.003625,
        "input_cache_miss": 0.435,    # 原价 $1.74
        "output": 0.87,                # 原价 $3.48
        "discount": True,
        "discount_pct": 75,
        "discount_until": "2026-05-31",
        "original_input_cache_hit": 0.0145,
        "original_input_cache_miss": 1.74,
        "original_output": 3.48,
    },
    "deepseek-chat": {  # 兼容旧名称 → flash
        "input_cache_hit": 0.0028,
        "input_cache_miss": 0.14,
        "output": 0.28,
    },
    "deepseek-reasoner": {  # 兼容旧名称 → flash thinking
        "input_cache_hit": 0.0028,
        "input_cache_miss": 0.14,
        "output": 0.28,
    },
}

DEFAULT_PRICING = {
    "input_cache_hit": 0.0,
    "input_cache_miss": 0.0,
    "output": 0.0,
}


def calc_cost(model, input_tokens, output_tokens, cache_read_tokens=0):
    """根据模型定价计算费用
    input_tokens: 缓存未命中的新 token (cache miss)
    cache_read_tokens: 缓存命中的 token (cache hit)
    """
    p = PRICING.get(model, DEFAULT_PRICING)

    cache_hit = cache_read_tokens or 0
    cache_miss = input_tokens or 0  # input_tokens 即为未命中部分

    cost = (
        cache_hit / 1_000_000 * p["input_cache_hit"] +
        cache_miss / 1_000_000 * p["input_cache_miss"] +
        (output_tokens or 0) / 1_000_000 * p["output"]
    )

    return {
        "cost": round(cost, 6),
        "cache_hit_tokens": cache_hit,
        "cache_miss_tokens": cache_miss,
        "output_tokens": output_tokens or 0,
        "has_discount": p.get("discount", False),
        "discount_pct": p.get("discount_pct", 0),
    }

HTML_PAGE = r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🌸 小珀 Token 监控</title>
<style>
  :root {
    --bg: #faf5ff;
    --card-bg: #ffffff;
    --text: #4a3670;
    --text-muted: #8b7fa8;
    --accent: #c084fc;
    --accent2: #e879f9;
    --accent3: #a78bfa;
    --border: #e9d5ff;
    --green: #34d399;
    --orange: #fb923c;
    --red: #f87171;
    --radius: 16px;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 20px;
  }
  .container { max-width: 1100px; margin: 0 auto; }

  /* Header */
  .header {
    text-align: center;
    padding: 30px 0 20px;
  }
  .header .avatar {
    font-size: 48px;
    margin-bottom: 8px;
    display: inline-block;
    animation: bounce 2s infinite;
  }
  @keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
  }
  .header h1 {
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent2), var(--accent3));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .header .subtitle {
    font-size: 14px;
    color: var(--text-muted);
    margin-top: 4px;
  }
  .header .refresh-badge {
    display: inline-block;
    margin-top: 10px;
    font-size: 12px;
    color: var(--accent);
    background: #f3e8ff;
    padding: 4px 12px;
    border-radius: 20px;
  }
  .header .refresh-badge .dot {
    display: inline-block;
    width: 6px; height: 6px;
    background: var(--accent2);
    border-radius: 50%;
    margin-right: 6px;
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  /* Stats Grid */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }
  .stat-card {
    background: var(--card-bg);
    border-radius: var(--radius);
    padding: 20px;
    box-shadow: 0 2px 12px rgba(167, 139, 250, 0.08);
    border: 1px solid var(--border);
    transition: transform 0.2s, box-shadow 0.2s;
  }
  .stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(167, 139, 250, 0.15);
  }
  .stat-card .label {
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 8px;
  }
  .stat-card .value {
    font-size: 28px;
    font-weight: 700;
    color: var(--text);
  }
  .stat-card .value.accent { color: var(--accent2); }
  .stat-card .value.green { color: var(--green); }
  .stat-card .value.orange { color: var(--orange); }
  .stat-card .sub {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
  }

  /* Section */
  .section {
    background: var(--card-bg);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 2px 12px rgba(167, 139, 250, 0.08);
    border: 1px solid var(--border);
  }
  .section h2 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 16px;
    color: var(--text);
  }

  /* Tables */
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }
  th, td {
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }
  th {
    color: var(--text-muted);
    font-weight: 500;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  td { color: var(--text); }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #faf5ff; }
  .mono { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px; }

  /* Bar */
  .bar-wrap {
    background: #f3e8ff;
    border-radius: 8px;
    height: 8px;
    overflow: hidden;
    margin-top: 4px;
  }
  .bar-fill {
    height: 100%;
    border-radius: 8px;
    background: linear-gradient(90deg, var(--accent2), var(--accent3));
    transition: width 0.6s ease;
  }

  /* Model tag */
  .model-tag {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    background: #f3e8ff;
    color: var(--accent3);
    font-weight: 500;
  }

  /* Footer */
  .footer {
    text-align: center;
    padding: 20px;
    color: var(--text-muted);
    font-size: 12px;
  }
  .footer .emoji { font-size: 16px; }

  /* Loading shimmer */
  @keyframes shimmer {
    0% { background-position: -200px 0; }
    100% { background-position: 200px 0; }
  }
  .loading {
    text-align: center;
    padding: 40px;
    color: var(--text-muted);
  }

  /* Cost highlight */
  .cost-positive { color: var(--green); }
  .cost-warning { color: var(--orange); }
  .total-row td {
    font-weight: 600;
    border-top: 2px solid var(--accent);
  }

  /* Responsive */
  @media (max-width: 640px) {
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    table { font-size: 12px; }
    th, td { padding: 8px; }
  }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="avatar">🌸</div>
    <h1>小珀 Token 监控面板</h1>
    <div class="subtitle">Hermes Agent · 实时用量追踪</div>
    <div class="refresh-badge">
      <span class="dot"></span>每 10 秒自动刷新 · <span id="last-update">--</span>
    </div>
  </div>

  <div class="stats-grid" id="stats-grid">
    <div class="loading">🌸 加载中～</div>
  </div>

  <div class="section">
    <h2>📋 会话记录</h2>
    <div id="sessions-table">
      <div class="loading">🌸 加载中～</div>
    </div>
  </div>

  <div class="section">
    <h2>🤖 模型用量</h2>
    <div id="models-table">
      <div class="loading">🌸 加载中～</div>
    </div>
  </div>

  <div class="footer">
    <span class="emoji">(◍•ᴗ•◍) </span> 小珀 为你监控中 · Hermes Agent Token Monitor
  </div>
</div>

<script>
async function fetchData() {
  try {
      const resp = await fetch('api/data');
    const data = await resp.json();
    render(data);
    document.getElementById('last-update').textContent =
      new Date().toLocaleTimeString('zh-CN');
  } catch (e) {
    console.error('Failed to fetch:', e);
  }
}

function fmtNum(n) {
  if (n == null) return '--';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toString();
}

function fmtCost(c) {
  if (c == null || c === 0) return '$0.00';
  if (c < 0.01) return '$' + c.toFixed(6);
  if (c < 1) return '$' + c.toFixed(4);
  return '$' + c.toFixed(2);
}

function render(data) {
  // Stats cards
  const s = data.summary;
  const discountTag = data.models.some(m => m.has_discount) ? ' 🔥75%off' : '';
  const totalEffectiveInput = (s.total_cache_read || 0) + (s.total_input || 0);
  const cacheHitRate = totalEffectiveInput > 0 ? (s.total_cache_read / totalEffectiveInput * 100).toFixed(1) : '0.0';
  const statsHTML = `
    <div class="stat-card">
      <div class="label">📊 总 Token 数</div>
      <div class="value accent">${fmtNum(s.total_tokens)}</div>
      <div class="sub">输入 ${fmtNum(s.total_input)} · 输出 ${fmtNum(s.total_output)}</div>
    </div>
    <div class="stat-card">
      <div class="label">💾 缓存命中率</div>
      <div class="value green">${cacheHitRate}%</div>
      <div class="sub">命中 ${fmtNum(s.total_cache_read)} · 未命中 ${fmtNum(Math.max(0, s.total_input - s.total_cache_read))}</div>
    </div>
    <div class="stat-card">
      <div class="label">💬 总会话 / 工具调用</div>
      <div class="value">${s.total_sessions} / ${s.total_tool_calls}</div>
      <div class="sub">活跃 ${s.active_days} 天 · 消息 ${s.total_messages} 条</div>
    </div>
    <div class="stat-card">
      <div class="label">💰 预估费用${discountTag}</div>
      <div class="value ${s.total_cost > 0.5 ? 'orange' : 'green'}">${fmtCost(s.total_cost)}</div>
      <div class="sub">基于 DeepSeek 官方定价</div>
    </div>
  `;
  document.getElementById('stats-grid').innerHTML = statsHTML;

  // Sessions table
  const sessionsHTML = `
    <table>
      <thead><tr>
        <th>时间</th><th>来源</th><th>模型</th><th>输入 (命中/未命中)</th><th>命中率</th><th>输出</th><th>费用</th>
      </tr></thead>
      <tbody>
        ${data.sessions.map(s => {
          const total = (s.input_tokens || 0) + (s.output_tokens || 0);
          const effInput = (s.cache_hit_tokens || 0) + (s.cache_miss_tokens || 0);
          const hitRate = effInput > 0 ? (s.cache_hit_tokens / effInput * 100).toFixed(1) : '0.0';
          const dt = s.started_at ? new Date(s.started_at * 1000).toLocaleString('zh-CN', {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '--';
          return `
          <tr>
            <td style="white-space:nowrap" title="${s.session_id}">${dt}</td>
            <td><span class="model-tag">${s.source || '--'}</span></td>
            <td class="mono">${(s.model || '--').substring(0, 22)}${s.has_discount ? ' 🔥' : ''}</td>
            <td>${fmtNum(s.cache_hit_tokens)} / ${fmtNum(s.cache_miss_tokens)}</td>
            <td><span style="color:var(--green);font-weight:600">${hitRate}%</span></td>
            <td>${fmtNum(s.output_tokens)}</td>
            <td style="color:${s.calculated_cost > 0.1 ? 'var(--orange)' : 'var(--text)'}">${fmtCost(s.calculated_cost)}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
    ${data.sessions.length === 0 ? '<p style="text-align:center;padding:20px;color:var(--text-muted)">还没有会话记录呢～</p>' : ''}
  `;
  document.getElementById('sessions-table').innerHTML = sessionsHTML;

  // Models table
  const modelsHTML = `
    <table>
      <thead><tr>
        <th>模型</th><th>会话</th><th>总 Token</th><th>输入</th><th>输出</th><th>命中率</th><th>费用</th>
      </tr></thead>
      <tbody>
        ${data.models.map(m => {
          const effInput = (m.cache_read_tokens || 0) + (m.input_tokens || 0);
          const hitRate = effInput > 0 ? ((m.cache_read_tokens || 0) / effInput * 100).toFixed(1) : '0.0';
          return `
          <tr>
            <td class="mono">${m.model}${m.has_discount ? ' 🔥' : ''}</td>
            <td>${m.sessions}</td>
            <td><strong>${fmtNum(m.total_tokens)}</strong></td>
            <td>${fmtNum(m.input_tokens)}</td>
            <td>${fmtNum(m.output_tokens)}</td>
            <td><span style="color:var(--green);font-weight:600">${hitRate}%</span></td>
            <td style="color:${m.cost > 0.1 ? 'var(--orange)' : 'var(--text)'}">${fmtCost(m.cost)}</td>
          </tr>`;
        }).join('')}
        ${data.models.length === 0 ? '<p style="text-align:center;padding:20px;color:var(--text-muted)">还没有模型用量数据～</p>' : ''}
      </tbody>
    </table>
  `;
  document.getElementById('models-table').innerHTML = modelsHTML;
}

// Initial fetch + auto refresh
fetchData();
setInterval(fetchData, 10000);
</script>
</body>
</html>
'''


def query_db():
    """查询 state.db 获取 token 用量数据"""
    if not os.path.exists(DB_PATH):
        return {"error": "数据库未找到"}

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Summary stats (raw from DB)
        cur.execute("""
            SELECT
                COUNT(*) as total_sessions,
                COALESCE(SUM(input_tokens), 0) as total_input,
                COALESCE(SUM(output_tokens), 0) as total_output,
                COALESCE(SUM(input_tokens), 0) + COALESCE(SUM(output_tokens), 0) as total_tokens,
                COALESCE(SUM(tool_call_count), 0) as total_tool_calls,
                COALESCE(SUM(message_count), 0) as total_messages,
                COALESCE(SUM(cache_read_tokens), 0) as total_cache_read,
                COALESCE(SUM(cache_write_tokens), 0) as total_cache_write,
                COALESCE(SUM(reasoning_tokens), 0) as total_reasoning
            FROM sessions
        """)
        summary = dict(cur.fetchone())

        # Active days
        cur.execute("""
            SELECT COUNT(DISTINCT date(started_at, 'unixepoch')) as active_days
            FROM sessions
        """)
        summary["active_days"] = cur.fetchone()["active_days"] or 0

        # Sessions list (most recent first) — 包含缓存数据用于费用计算
        cur.execute("""
            SELECT id as session_id, source, model, input_tokens, output_tokens,
                   cache_read_tokens, cache_write_tokens, reasoning_tokens,
                   tool_call_count, message_count, estimated_cost_usd,
                   actual_cost_usd, started_at, ended_at, title
            FROM sessions
            ORDER BY started_at DESC
            LIMIT 50
        """)
        sessions_raw = [dict(row) for row in cur.fetchall()]

        # 逐会话计算实际费用
        sessions = []
        total_calculated_cost = 0.0
        for s in sessions_raw:
            cost_info = calc_cost(
                s.get("model", ""),
                s.get("input_tokens", 0),
                s.get("output_tokens", 0),
                s.get("cache_read_tokens", 0),
            )
            s["calculated_cost"] = cost_info["cost"]
            s["cache_hit_tokens"] = cost_info["cache_hit_tokens"]
            s["cache_miss_tokens"] = cost_info["cache_miss_tokens"]
            s["has_discount"] = cost_info["has_discount"]
            total_calculated_cost += cost_info["cost"]
            sessions.append(s)

        summary["total_cost"] = round(total_calculated_cost, 6)

        # Model breakdown — 含费用
        cur.execute("""
            SELECT
                model,
                COUNT(*) as sessions,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens,
                COALESCE(SUM(cache_read_tokens), 0) as cache_read_tokens,
                COALESCE(SUM(input_tokens), 0) + COALESCE(SUM(output_tokens), 0) as total_tokens
            FROM sessions
            GROUP BY model
            ORDER BY total_tokens DESC
        """)
        models_raw = [dict(row) for row in cur.fetchall()]

        models = []
        for m in models_raw:
            cost_info = calc_cost(
                m.get("model", ""),
                m.get("input_tokens", 0),
                m.get("output_tokens", 0),
                m.get("cache_read_tokens", 0),
            )
            m["cost"] = cost_info["cost"]
            m["has_discount"] = cost_info["has_discount"]
            m["discount_pct"] = cost_info["discount_pct"]
            models.append(m)

        conn.close()

        return {
            "summary": summary,
            "sessions": sessions,
            "models": models,
            "updated_at": int(time.time()),
        }

    except Exception as e:
        return {"error": str(e)}


class TokenMonitorHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 减少日志输出

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/data":
            data = query_db()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "time": int(time.time())}).encode())
            return

        # Default: serve the HTML page
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode("utf-8"))


def main():
    server = http.server.ThreadingHTTPServer((HOST, PORT), TokenMonitorHandler)
    print(f"🌸 小珀 Token Monitor 启动成功！")
    print(f"   地址: http://{HOST}:{PORT}")
    print(f"   数据源: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
