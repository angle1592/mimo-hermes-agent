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

# 人民币汇率（CNY per USD）
USD_TO_CNY = 6.85

# DeepSeek 官方定价 - 每百万 Token (USD)
# 来源: https://api-docs.deepseek.com/quick_start/pricing
PRICING = {
    "deepseek-v4-flash": {
        "input_cache_hit": 0.0028,
        "input_cache_miss": 0.14,
        "output": 0.28,
    },
    "deepseek-v4-pro": {
        # 75% 折扣至 2026/05/31 15:59 UTC
        "input_cache_hit": 0.003625,
        "input_cache_miss": 0.435,
        "output": 0.87,
        "discount": True,
        "discount_pct": 75,
        "discount_until": "2026-05-31",
        "original_input_cache_hit": 0.0145,
        "original_input_cache_miss": 1.74,
        "original_output": 3.48,
    },
    "deepseek-chat": {  # 旧名称 → deepseek-v4-flash
        "input_cache_hit": 0.0028,
        "input_cache_miss": 0.14,
        "output": 0.28,
        "display_name": "deepseek-v4-flash",
    },
    "deepseek-reasoner": {  # 旧名称 → deepseek-v4-flash thinking
        "input_cache_hit": 0.0028,
        "input_cache_miss": 0.14,
        "output": 0.28,
        "display_name": "deepseek-v4-flash",
    },
    # Xiaomi MiMo 定价 (海外 USD，input ≤ 256K)
    # 来源: https://platform.xiaomimimo.com/docs/en-US/pricing
    "mimo-v2.5-pro": {
        "input_cache_hit": 0.20,
        "input_cache_miss": 1.00,
        "output": 3.00,
        "vendor": "Xiaomi",
    },
    "mimo-v2-pro": {
        "input_cache_hit": 0.20,
        "input_cache_miss": 1.00,
        "output": 3.00,
        "display_name": "mimo-v2.5-pro",
        "vendor": "Xiaomi",
    },
    "xiaomi/mimo-v2.5": {
        "input_cache_hit": 0.08,
        "input_cache_miss": 0.40,
        "output": 2.00,
        "display_name": "mimo-v2.5",
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

DEFAULT_PRICING = {
    "input_cache_hit": 0.0,
    "input_cache_miss": 0.0,
    "output": 0.0,
}

# 当数据库中出现未知模型时使用的兜底定价（按照 deepseek-v4-flash 价格估算）
UNKNOWN_MODEL_PRICING = {
    "input_cache_hit": 0.0028,
    "input_cache_miss": 0.14,
    "output": 0.28,
}


def calc_cost(model, input_tokens, output_tokens, cache_read_tokens=0):
    """根据模型定价计算费用（返回 USD）"""
    # 标准化模型名
    normalized = model
    if model in ("deepseek-chat", "deepseek-reasoner"):
        normalized = "deepseek-v4-flash"
    elif model in ("mimo-v2-pro",):
        normalized = "mimo-v2.5-pro"
    elif model in ("xiaomi/mimo-v2.5",):
        normalized = "mimo-v2.5"
    p = PRICING.get(normalized, UNKNOWN_MODEL_PRICING)
    cache_hit = cache_read_tokens or 0
    cache_miss = input_tokens or 0
    cost = (
        cache_hit / 1_000_000 * p["input_cache_hit"] +
        cache_miss / 1_000_000 * p["input_cache_miss"] +
        (output_tokens or 0) / 1_000_000 * p["output"]
    )
    return {
        "cost": round(cost, 6),
        "cost_cny": round(cost * USD_TO_CNY, 6),
        "cache_hit_tokens": cache_hit,
        "cache_miss_tokens": cache_miss,
        "output_tokens": output_tokens or 0,
        "has_discount": p.get("discount", False),
        "discount_pct": p.get("discount_pct", 0),
        "display_name": p.get("display_name", model),
    }


HTML_PAGE = r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>💰 小珀 Token 监控</title>
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

  .header {
    text-align: center;
    padding: 30px 0 20px;
  }
  .header .avatar { font-size: 48px; margin-bottom: 8px; display: inline-block; animation: bounce 2s infinite; }
  @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
  .header h1 {
    font-size: 28px; font-weight: 700;
    background: linear-gradient(135deg, var(--accent2), var(--accent3));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  }
  .header .subtitle { font-size: 14px; color: var(--text-muted); margin-top: 4px; }
  .header .refresh-badge {
    display: inline-block; margin-top: 10px; font-size: 12px; color: var(--accent);
    background: #f3e8ff; padding: 4px 12px; border-radius: 20px;
  }
  .header .refresh-badge .dot {
    display: inline-block; width: 6px; height: 6px; background: var(--accent2);
    border-radius: 50%; margin-right: 6px; animation: pulse 2s infinite;
  }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .stat-card {
    background: var(--card-bg); border-radius: var(--radius); padding: 20px;
    box-shadow: 0 2px 12px rgba(167, 139, 250, 0.08); border: 1px solid var(--border);
    transition: transform 0.2s, box-shadow 0.2s;
  }
  .stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(167, 139, 250, 0.15); }
  .stat-card .label { font-size: 13px; color: var(--text-muted); margin-bottom: 8px; }
  .stat-card .value { font-size: 28px; font-weight: 700; color: var(--text); }
  .stat-card .value.accent { color: var(--accent2); }
  .stat-card .value.green { color: var(--green); }
  .stat-card .value.orange { color: var(--orange); }
  .stat-card .value.pink { color: #f472b6; }
  .stat-card .sub { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

  .section {
    background: var(--card-bg); border-radius: var(--radius); padding: 24px;
    margin-bottom: 20px; box-shadow: 0 2px 12px rgba(167, 139, 250, 0.08); border: 1px solid var(--border);
  }
  .section h2 { font-size: 18px; font-weight: 600; margin-bottom: 16px; color: var(--text); }
  .section-header-bar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }

  /* --- Filter bar --- */
  .filter-bar {
    display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
    padding: 12px 16px; background: #faf5ff; border-radius: 12px;
    margin-bottom: 16px; border: 1px solid var(--border);
  }
  .filter-bar input, .filter-bar select {
    padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px;
    font-size: 13px; background: white; color: var(--text); outline: none;
    font-family: inherit;
  }
  .filter-bar input:focus, .filter-bar select:focus { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(192,132,252,0.15); }
  .filter-bar input { flex: 1; min-width: 160px; }
  .filter-bar select { min-width: 100px; }
  .filter-bar .badge { font-size: 12px; color: var(--text-muted); background: white; padding: 4px 10px; border-radius: 12px; border: 1px solid var(--border); }

  /* --- Date group --- */
  .date-group { margin-bottom: 8px; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
  .date-group-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 16px; cursor: pointer; user-select: none;
    background: #faf5ff; transition: background 0.15s; font-size: 14px;
  }
  .date-group-header:hover { background: #f3e8ff; }
  .date-group-header .left { display: flex; align-items: center; gap: 10px; }
  .date-group-header .chevron { transition: transform 0.2s; font-size: 12px; color: var(--text-muted); }
  .date-group-header .chevron.open { transform: rotate(90deg); }
  .date-group-header .label { font-weight: 600; color: var(--text); }
  .date-group-header .date-str { font-size: 12px; color: var(--text-muted); }
  .date-group-header .group-summary { font-size: 12px; color: var(--text-muted); display: flex; gap: 12px; }
  .date-group-body { display: none; }
  .date-group-body.open { display: block; }

  /* --- Sessions table --- */
  .session-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .session-table th {
    padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border);
    color: var(--text-muted); font-weight: 500; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.5px; cursor: pointer; user-select: none;
    white-space: nowrap; position: sticky; top: 0; background: white;
  }
  .session-table th:hover { color: var(--accent3); }
  .session-table th .sort-icon { margin-left: 3px; font-size: 10px; opacity: 0.4; }
  .session-table th .sort-icon.active { opacity: 1; }
  .session-table td { padding: 8px 10px; border-bottom: 1px solid #f3e8ff; color: var(--text); }
  .session-table tr:hover td { background: #faf5ff; }
  .session-table .mono { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 11px; }
  .model-tag-s { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; background: #f3e8ff; color: var(--accent3); font-weight: 500; }

  /* --- Load more --- */
  .load-more {
    display: block; width: 100%; padding: 12px; margin-top: 8px;
    border: 1px dashed var(--border); border-radius: 10px;
    background: transparent; color: var(--accent3); font-size: 13px; cursor: pointer;
    text-align: center; transition: all 0.15s; font-family: inherit;
  }
  .load-more:hover { background: #f3e8ff; border-color: var(--accent); }

  /* --- Models table --- */
  .models-table { width: 100%; border-collapse: collapse; font-size: 14px; }
  .models-table th, .models-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }
  .models-table th { color: var(--text-muted); font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
  .models-table td { color: var(--text); }
  .models-table tr:last-child td { border-bottom: none; }
  .models-table tr:hover td { background: #faf5ff; }

  .footer { text-align: center; padding: 20px; color: var(--text-muted); font-size: 12px; }
  .footer .emoji { font-size: 16px; }

  .loading { text-align: center; padding: 40px; color: var(--text-muted); }
  .empty-state { text-align: center; padding: 30px; color: var(--text-muted); }

  @media (max-width: 640px) {
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .session-table { font-size: 12px; }
    .session-table th, .session-table td { padding: 6px; }
    .filter-bar input, .filter-bar select { font-size: 12px; padding: 6px 10px; }
  }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="avatar">💰</div>
    <h1>小珀 Token 监控面板</h1>
    <div class="subtitle">Hermes Agent · 实时用量追踪 · DeepSeek + Xiaomi MiMo · 以人民币计价</div>
    <div class="refresh-badge">
      <span class="dot"></span>每 10 秒自动刷新 · <span id="last-update">--</span>
    </div>
  </div>

  <div class="stats-grid" id="stats-grid">
    <div class="loading">💰 加载中～</div>
  </div>

  <div class="section">
    <div class="section-header-bar">
      <h2>📋 会话记录</h2>
      <span id="session-count" style="font-size:13px;color:var(--text-muted)"></span>
    </div>

    <!-- Filter bar -->
    <div class="filter-bar" id="filter-bar">
      <input type="text" id="search-input" placeholder="🔍 搜索会话 ID、来源、模型..." oninput="applyFilters()">
      <select id="model-filter" onchange="applyFilters()">
        <option value="">全部模型</option>
      </select>
      <select id="source-filter" onchange="applyFilters()">
        <option value="">全部来源</option>
      </select>
      <select id="sort-select" onchange="applyFilters()">
        <option value="time-desc">最新优先</option>
        <option value="time-asc">最早优先</option>
        <option value="cost-desc">费用从高到低</option>
        <option value="cost-asc">费用从低到高</option>
        <option value="output-desc">输出 Token 从高到低</option>
        <option value="output-asc">输出 Token 从低到高</option>
      </select>
      <span class="badge" id="filter-count"></span>
    </div>

    <div id="sessions-container">
      <div class="loading">💰 加载中～</div>
    </div>
  </div>

  <div class="section">
    <h2>🤖 模型用量（按 Gateway 记录）</h2>
    <div id="models-table">
      <div class="loading">💰 加载中～</div>
    </div>
  </div>

  <div class="section">
    <h2>💰 模型单价 (每百万 Token · ≤256K 上下文 · 人民币)</h2>
    <div id="pricing-table">
      <div class="loading">💰 加载中～</div>
    </div>
    <div style="font-size:12px;color:var(--text-muted);margin-top:12px;line-height:1.8">
      汇率 ¥6.85/USD · 定价来源:
      <a href="https://api-docs.deepseek.com/quick_start/pricing" target="_blank" style="color:var(--accent3)">DeepSeek</a> ·
      <a href="https://platform.xiaomimimo.com/docs/en-US/pricing" target="_blank" style="color:var(--accent3)">Xiaomi MiMo</a><br>
      MiMo 256K-1M 大上下文区间价格约为上表的 2 倍（缓存命中/未命中/输出均翻倍）<br>
      MiMo 缓存写入限时免费 · DeepSeek v4-pro 75% 折扣至 2026/05/31
    </div>
  </div>

  <div class="footer">
    <span class="emoji">(◍•ᴗ•◍) </span> 小珀 为你监控中 · 汇率 ¥6.85/USD · DeepSeek + Xiaomi MiMo 官方定价
  </div>
</div>

<script>
// ─── State ───────────────────────────────────────────
const PAGE_SIZE = 20;
let allSessions = [];
let shownCount = 0;

// ─── Format helpers ──────────────────────────────────
function fmtNum(n) {
  if (n == null) return '--';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toString();
}
function fmtCostCNY(cny) {
  if (cny == null || cny === 0) return '¥0.00';
  if (cny < 0.01) return '¥' + cny.toFixed(6);
  if (cny < 1) return '¥' + cny.toFixed(4);
  if (cny < 100) return '¥' + cny.toFixed(2);
  return '¥' + cny.toFixed(2);
}
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

// ─── Group sessions ──────────────────────────────────
function groupSessions(sessions) {
  const groups = {};
  const order = ['今天', '昨天', '这周', '最近 7 天', '最近 30 天', '更早'];
  for (const s of sessions) {
    const label = getDateLabel(s.started_at);
    if (!groups[label]) groups[label] = [];
    groups[label].push(s);
  }
  return order.filter(k => groups[k]).map(k => ({ label: k, sessions: groups[k] }));
}

// ─── Sort sessions ───────────────────────────────────
function sortSessions(sessions, sortKey) {
  const copy = [...sessions];
  const key = sortKey || 'time-desc';
  const [field, dir] = key.split('-');
  const mult = dir === 'desc' ? -1 : 1;
  copy.sort((a, b) => {
    let va, vb;
    switch (field) {
      case 'time': va = a.started_at || 0; vb = b.started_at || 0; break;
      case 'cost': va = a.calculated_cost_cny || 0; vb = b.calculated_cost_cny || 0; break;
      case 'output': va = a.output_tokens || 0; vb = b.output_tokens || 0; break;
      default: va = a.started_at || 0; vb = b.started_at || 0; dir = 'desc';
    }
    return (va - vb) * mult;
  });
  // After sorting, re-group
  return copy;
}

// ─── Apply filters ───────────────────────────────────
function applyFilters() {
  const search = (document.getElementById('search-input').value || '').trim().toLowerCase();
  const modelFilter = document.getElementById('model-filter').value;
  const sourceFilter = document.getElementById('source-filter').value;
  const sortKey = document.getElementById('sort-select').value;

  let filtered = allSessions.filter(s => {
    if (search && !s.session_id?.toLowerCase().includes(search) &&
        !(s.source || '').toLowerCase().includes(search) &&
        !(s.model || '').toLowerCase().includes(search) &&
        !(s.model_display || '').toLowerCase().includes(search)) return false;
    if (modelFilter && s.model !== modelFilter && s.model_display !== modelFilter) return false;
    if (sourceFilter && s.source !== sourceFilter) return false;
    return true;
  });

  filtered = sortSessions(filtered, sortKey);
  document.getElementById('filter-count').textContent = `${filtered.length} 条记录`;

  // Update session total display
  document.getElementById('session-count').textContent =
    `共 ${allSessions.length} 条，已筛选 ${filtered.length} 条`;

  renderGroupedSessions(filtered, true);
}

// ─── Render grouped sessions ─────────────────────────
function renderGroupedSessions(sessions, reset) {
  if (reset) shownCount = 0;
  const grouped = groupSessions(sessions);

  let totalShown = 0;
  let html = '';
  for (const group of grouped) {
    if (totalShown >= PAGE_SIZE) {
      // Not shown yet — will be handled by load more
      break;
    }
    const remaining = PAGE_SIZE - totalShown;
    const groupSessions = group.sessions.slice(0, remaining);
    totalShown += groupSessions.length;
    const totalSessions = group.sessions.length;
    const totalCost = groupSessions.reduce((acc, s) => acc + (s.calculated_cost_cny || 0), 0);
    const groupTotalCost = group.sessions.reduce((acc, s) => acc + (s.calculated_cost_cny || 0), 0);
    const dateStr = groupSessions[0]?.started_at ? new Date(groupSessions[0].started_at * 1000).toLocaleDateString('zh-CN') : '';

    html += `<div class="date-group">
      <div class="date-group-header" onclick="toggleGroup(this)">
        <div class="left">
          <span class="chevron open">▶</span>
          <span class="label">${group.label}</span>
          <span class="date-str">${dateStr}</span>
        </div>
        <div class="group-summary">
          <span>📋 ${totalSessions} 条</span>
          <span>💰 ${fmtCostCNY(groupTotalCost)}</span>
        </div>
      </div>
      <div class="date-group-body open">
        <table class="session-table">
          <thead><tr>
            <th>时间</th><th>来源</th><th>模型</th><th>输入(命中/未命中)</th><th>命中率</th><th>输出</th><th>费用(CNY)</th>
          </tr></thead>
          <tbody>
            ${groupSessions.map(s => {
              const effInput = (s.cache_hit_tokens || 0) + (s.cache_miss_tokens || 0);
              const hitRate = effInput > 0 ? (s.cache_hit_tokens / effInput * 100).toFixed(1) : '0.0';
              const dt = s.started_at ? new Date(s.started_at * 1000).toLocaleString('zh-CN', {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '--';
              return `<tr>
                <td style="white-space:nowrap" title="${s.session_id}">${dt}</td>
                <td><span class="model-tag-s">${s.source || '--'}</span></td>
                <td class="mono">${(s.model_display || s.model || '--').substring(0, 22)}${s.has_discount ? ' 🔥' : ''}</td>
                <td class="mono">${fmtNum(s.cache_hit_tokens)} / ${fmtNum(s.cache_miss_tokens)}</td>
                <td><span style="color:var(--green);font-weight:600">${hitRate}%</span></td>
                <td class="mono">${fmtNum(s.output_tokens)}</td>
                <td style="color:${s.calculated_cost_cny > 1 ? 'var(--orange)' : 'var(--text)'}">${fmtCostCNY(s.calculated_cost_cny)}</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>`;
  }

  const totalAvailable = sessions.length;
  const remaining = totalAvailable - totalShown;

  if (remaining > 0) {
    html += `<button class="load-more" onclick="loadMore()">📥 加载更多（还有 ${remaining} 条）</button>`;
  } else if (totalAvailable > 0) {
    html += `<div style="text-align:center;padding:12px;color:var(--text-muted);font-size:13px;">✅ 已显示全部 ${totalAvailable} 条记录</div>`;
  }

  document.getElementById('sessions-container').innerHTML = html ||
    '<div class="empty-state">🔍 没有匹配的会话记录</div>';
  shownCount = totalShown;
}

function toggleGroup(header) {
  const chevron = header.querySelector('.chevron');
  const body = header.nextElementSibling;
  chevron.classList.toggle('open');
  body.classList.toggle('open');
}

function loadMore() {
  const sortKey = document.getElementById('sort-select').value;
  const search = document.getElementById('search-input').value.trim().toLowerCase();
  const modelFilter = document.getElementById('model-filter').value;
  const sourceFilter = document.getElementById('source-filter').value;

  let filtered = allSessions.filter(s => {
    if (search && !s.session_id?.toLowerCase().includes(search) &&
        !(s.source || '').toLowerCase().includes(search) &&
        !(s.model || '').toLowerCase().includes(search)) return false;
    if (modelFilter && s.model !== modelFilter && s.model_display !== modelFilter) return false;
    if (sourceFilter && s.source !== sourceFilter) return false;
    return true;
  });
  filtered = sortSessions(filtered, sortKey);

  // Increase PAGE_SIZE effectively
  shownCount += PAGE_SIZE;
  renderGroupedSessions(filtered, true);
}

// ─── Render main ─────────────────────────────────────
function render(data) {
  // Stats cards
  const s = data.summary;
  const discountTag = data.models.some(m => m.has_discount) ? ' 🔥75%off' : '';
  const totalEffectiveInput = (s.total_cache_read || 0) + (s.total_input || 0);
  const cacheHitRate = totalEffectiveInput > 0 ? (s.total_cache_read / totalEffectiveInput * 100).toFixed(1) : '0.0';

  const statsHTML = `
    <div class="stat-card">
      <div class="label">📊 总 Token 数（含缓存）</div>
      <div class="value accent">${fmtNum(s.total_tokens)}</div>
      <div class="sub">命中 ${fmtNum(s.total_cache_read)} + 未命中 ${fmtNum(Math.max(0, s.total_input))} + 输出 ${fmtNum(s.total_output)}</div>
    </div>
    <div class="stat-card">
      <div class="label">💾 缓存命中率</div>
      <div class="value green">${cacheHitRate}%</div>
      <div class="sub">命中 ${fmtNum(s.total_cache_read)} · 未命中 ${fmtNum(Math.max(0, s.total_input))}</div>
    </div>
    <div class="stat-card">
      <div class="label">💬 总会话 / 工具调用</div>
      <div class="value">${s.total_sessions} / ${s.total_tool_calls}</div>
      <div class="sub">活跃 ${s.active_days} 天 · 消息 ${s.total_messages} 条</div>
    </div>
    <div class="stat-card">
      <div class="label">💰 预估费用（Gateway 记录）${discountTag}</div>
      <div class="value ${s.total_cost_cny > 3 ? 'orange' : 'green'}">${fmtCostCNY(s.total_cost_cny)}</div>
      <div class="sub">≈ $${(s.total_cost_cny / 6.85).toFixed(4)} USD · 基于 DeepSeek 官方定价</div>
    </div>
  `;
  document.getElementById('stats-grid').innerHTML = statsHTML;

  // Store sessions globally
  allSessions = data.sessions || [];

  // Populate filter dropdowns
  const modelSelect = document.getElementById('model-filter');
  const sourceSelect = document.getElementById('source-filter');
  const currentModel = modelSelect.value;
  const currentSource = sourceSelect.value;

  const models = [...new Set(allSessions.map(s => s.model_display || s.model).filter(Boolean))];
  const sources = [...new Set(allSessions.map(s => s.source).filter(Boolean))];

  modelSelect.innerHTML = '<option value="">全部模型</option>' +
    models.map(m => `<option value="${m}" ${m === currentModel ? 'selected' : ''}>${m}</option>`).join('');
  sourceSelect.innerHTML = '<option value="">全部来源</option>' +
    sources.map(s => `<option value="${s}" ${s === currentSource ? 'selected' : ''}>${s}</option>`).join('');

  document.getElementById('session-count').textContent = `共 ${allSessions.length} 条`;

  // Apply filters and render
  applyFilters();

  // Models table
  const modelsHTML = `
    <table class="models-table">
      <thead><tr>
        <th>模型</th><th>会话</th><th>总 Token</th><th>输入</th><th>输出</th><th>命中率</th><th>费用(CNY)</th>
      </tr></thead>
      <tbody>
        ${data.models.map(m => {
          const effInput = (m.cache_read_tokens || 0) + (m.input_tokens || 0);
          const hitRate = effInput > 0 ? ((m.cache_read_tokens || 0) / effInput * 100).toFixed(1) : '0.0';
          return `<tr>
            <td class="mono">${m.model}${m.has_discount ? ' 🔥' : ''}${m.vendor === 'Xiaomi' ? ' <span style="display:inline-block;padding:1px 6px;border-radius:8px;font-size:10px;background:#fff3e0;color:#e65100;font-weight:500">Xiaomi</span>' : ''}</td>
            <td>${m.sessions}</td>
            <td><strong>${fmtNum(m.total_tokens)}</strong></td>
            <td>${fmtNum(m.input_tokens)} <span style="font-size:11px;color:var(--text-muted)">未命中</span><br><span style="font-size:11px;color:var(--text-muted)">命中 ${fmtNum(m.cache_read_tokens)}</span></td>
            <td>${fmtNum(m.output_tokens)}</td>
            <td><span style="color:var(--green);font-weight:600">${hitRate}%</span></td>
            <td style="color:${m.cost_cny > 1 ? 'var(--orange)' : 'var(--text)'}">${fmtCostCNY(m.cost_cny)}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  `;
  document.getElementById('models-table').innerHTML = modelsHTML;

  // Pricing table
  const pricing = data.pricing || [];
  const usdToCny = 6.85;
  const pricingHTML = `
    <table class="models-table">
      <thead><tr>
        <th>模型</th>
        <th>输入 (缓存命中)</th>
        <th>输入 (缓存未命中)</th>
        <th>输出</th>
        <th>状态</th>
      </tr></thead>
      <tbody>
        ${pricing.map(p => {
          const hasDiscount = p.has_discount;
          const cny = p.price_cny || {};
          // CNY as primary display, USD as secondary
          const hitCell = hasDiscount
            ? `<span style="color:var(--green)"><strong>¥${cny.input_cache_hit}</strong></span> <span style="font-size:11px;color:var(--text-muted);text-decoration:line-through">¥${(p.original_input_cache_hit * usdToCny).toFixed(3)}</span><br><span style="font-size:11px;color:var(--text-muted)">≈ $${p.input_cache_hit}</span>`
            : `<strong>¥${cny.input_cache_hit}</strong><br><span style="font-size:11px;color:var(--text-muted)">≈ $${p.input_cache_hit}</span>`;
          const missCell = hasDiscount
            ? `<span style="color:var(--green)"><strong>¥${cny.input_cache_miss}</strong></span> <span style="font-size:11px;color:var(--text-muted);text-decoration:line-through">¥${(p.original_input_cache_miss * usdToCny).toFixed(3)}</span><br><span style="font-size:11px;color:var(--text-muted)">≈ $${p.input_cache_miss}</span>`
            : `<strong>¥${cny.input_cache_miss}</strong><br><span style="font-size:11px;color:var(--text-muted)">≈ $${p.input_cache_miss}</span>`;
          const outCell = hasDiscount
            ? `<span style="color:var(--green)"><strong>¥${cny.output}</strong></span> <span style="font-size:11px;color:var(--text-muted);text-decoration:line-through">¥${(p.original_output * usdToCny).toFixed(3)}</span><br><span style="font-size:11px;color:var(--text-muted)">≈ $${p.output}</span>`
            : `<strong>¥${cny.output}</strong><br><span style="font-size:11px;color:var(--text-muted)">≈ $${p.output}</span>`;
          const discountNote = hasDiscount
            ? `<span style="font-size:11px;color:var(--orange)">🔥${p.discount_pct}% 折扣至 ${p.discount_until}</span>`
            : '<span style="font-size:11px;color:var(--text-muted)">标准定价</span>';
          const vendorTag = p.vendor === 'Xiaomi'
            ? '<span style="display:inline-block;padding:1px 6px;border-radius:8px;font-size:10px;background:#fff3e0;color:#e65100;margin-left:6px;font-weight:500">Xiaomi</span>'
            : '<span style="display:inline-block;padding:1px 6px;border-radius:8px;font-size:10px;background:#e8f5e9;color:#2e7d32;margin-left:6px;font-weight:500">DeepSeek</span>';
          return `<tr>
            <td class="mono"><strong>${p.model}</strong>${vendorTag}</td>
            <td class="mono">${hitCell}</td>
            <td class="mono">${missCell}</td>
            <td class="mono">${outCell}</td>
            <td>${discountNote}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  `;
  document.getElementById('pricing-table').innerHTML = pricingHTML;
}

// ─── Fetch ───────────────────────────────────────────
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

fetchData();
setInterval(fetchData, 10000);
</script>
</body>
</html>
'''


def query_db():
    """查询 state.db 获取 token 用量数据

    Returns a dict with data on success, or raises an exception on failure.
    Raises FileNotFoundError if the database file does not exist.
    Raises sqlite3.Error on database access failures.
    """
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"数据库未找到: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT
                COUNT(*) as total_sessions,
                COALESCE(SUM(input_tokens), 0) as total_input,
                COALESCE(SUM(output_tokens), 0) as total_output,
                COALESCE(SUM(input_tokens), 0) + COALESCE(SUM(output_tokens), 0) + COALESCE(SUM(cache_read_tokens), 0) as total_tokens,
                COALESCE(SUM(tool_call_count), 0) as total_tool_calls,
                COALESCE(SUM(message_count), 0) as total_messages,
                COALESCE(SUM(cache_read_tokens), 0) as total_cache_read,
                COALESCE(SUM(cache_write_tokens), 0) as total_cache_write,
                COALESCE(SUM(reasoning_tokens), 0) as total_reasoning
            FROM sessions
        """)
        summary = dict(cur.fetchone())

        cur.execute("""
            SELECT COUNT(DISTINCT date(started_at, 'unixepoch')) as active_days
            FROM sessions
        """)
        summary["active_days"] = cur.fetchone()["active_days"] or 0

        cur.execute("""
            SELECT id as session_id, source, model, input_tokens, output_tokens,
                   cache_read_tokens, cache_write_tokens, reasoning_tokens,
                   tool_call_count, message_count, estimated_cost_usd,
                   actual_cost_usd, started_at, ended_at, title
            FROM sessions
            ORDER BY started_at DESC
            LIMIT 500
        """)
        sessions_raw = [dict(row) for row in cur.fetchall()]
        # 逐会话计算实际费用
        sessions = []
        total_calculated_cost_cny = 0.0
        for s in sessions_raw:
            model_raw = s.get("model", "")
            model_display = PRICING.get(model_raw, {}).get("display_name", model_raw)
            cost_info = calc_cost(
                model_raw,
                s.get("input_tokens", 0),
                s.get("output_tokens", 0),
                s.get("cache_read_tokens", 0),
            )
            s["calculated_cost"] = cost_info["cost"]
            s["calculated_cost_cny"] = cost_info["cost_cny"]
            s["cache_hit_tokens"] = cost_info["cache_hit_tokens"]
            s["cache_miss_tokens"] = cost_info["cache_miss_tokens"]
            s["has_discount"] = cost_info["has_discount"]
            s["model_display"] = model_display
            total_calculated_cost_cny += cost_info["cost_cny"]
            sessions.append(s)

        summary["total_cost"] = round(total_calculated_cost_cny / USD_TO_CNY, 6)
        summary["total_cost_cny"] = round(total_calculated_cost_cny, 6)

        # 额外聚合：从全部会话计算总费用（不依赖 LIMIT 500）
        cur.execute("""
            SELECT
                CASE
                    WHEN model IN ('deepseek-chat', 'deepseek-reasoner') THEN 'deepseek-v4-flash'
                    WHEN model IN ('mimo-v2-pro') THEN 'mimo-v2.5-pro'
                    WHEN model IN ('xiaomi/mimo-v2.5') THEN 'mimo-v2.5'
                    ELSE model
                END as display_model,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens,
                COALESCE(SUM(cache_read_tokens), 0) as cache_read_tokens
            FROM sessions
            GROUP BY display_model
        """)
        all_cost_cny = 0.0
        for row in cur.fetchall():
            ci = calc_cost(row["display_model"], row["input_tokens"], row["output_tokens"], row["cache_read_tokens"])
            all_cost_cny += ci["cost_cny"]
        summary["total_cost"] = round(all_cost_cny / USD_TO_CNY, 6)
        summary["total_cost_cny"] = round(all_cost_cny, 6)

        # Model breakdown — 合并 deepseek-chat/reasoner 到 flash
        cur.execute("""
            SELECT
                CASE
                    WHEN model IN ('deepseek-chat', 'deepseek-reasoner') THEN 'deepseek-v4-flash'
                    WHEN model IN ('mimo-v2-pro') THEN 'mimo-v2.5-pro'
                    WHEN model IN ('xiaomi/mimo-v2.5') THEN 'mimo-v2.5'
                    ELSE model
                END as display_model,
                COUNT(*) as sessions,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens,
                COALESCE(SUM(cache_read_tokens), 0) as cache_read_tokens,
                COALESCE(SUM(input_tokens), 0) + COALESCE(SUM(output_tokens), 0) + COALESCE(SUM(cache_read_tokens), 0) as total_tokens
            FROM sessions
            GROUP BY display_model
            ORDER BY total_tokens DESC
        """)
        models_raw = [dict(row) for row in cur.fetchall()]

        models = []
        for m in models_raw:
            cost_info = calc_cost(
                m.get("display_model", ""),
                m.get("input_tokens", 0),
                m.get("output_tokens", 0),
                m.get("cache_read_tokens", 0),
            )
            m["cost"] = cost_info["cost"]
            m["cost_cny"] = cost_info["cost_cny"]
            m["has_discount"] = cost_info["has_discount"]
            m["discount_pct"] = cost_info["discount_pct"]
            m["model"] = m.get("display_model", "")
            m["vendor"] = PRICING.get(m["model"], {}).get("vendor", "DeepSeek")
            models.append(m)

        # Build pricing info for frontend
        pricing_export = []
        seen = set()
        # 用户期望的近似人民币显示值
        CNY_DISPLAY = {
            "deepseek-v4-flash": {"input_cache_hit": 0.02, "input_cache_miss": 1, "output": 2},
            "deepseek-v4-pro": {"input_cache_hit": 0.025, "input_cache_miss": 3, "output": 6},
            "mimo-v2.5-pro": {"input_cache_hit": 1.40, "input_cache_miss": 7, "output": 21},
            "mimo-v2.5": {"input_cache_hit": 0.56, "input_cache_miss": 2.80, "output": 14},
            "mimo-v2-flash": {"input_cache_hit": 0.07, "input_cache_miss": 0.70, "output": 2.10},
        }
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
                "price_cny": CNY_DISPLAY.get(display, {}),
                "vendor": p.get("vendor", "DeepSeek"),
            }
            if p.get("discount"):
                entry["has_discount"] = True
                entry["discount_pct"] = p["discount_pct"]
                entry["discount_until"] = p.get("discount_until", "")
                entry["original_input_cache_hit"] = p.get("original_input_cache_hit")
                entry["original_input_cache_miss"] = p.get("original_input_cache_miss")
                entry["original_output"] = p.get("original_output")
            pricing_export.append(entry)

        return {
            "summary": summary,
            "sessions": sessions,
            "models": models,
            "pricing": pricing_export,
            "updated_at": int(time.time()),
        }
    finally:
        conn.close()


class TokenMonitorHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/data":
            try:
                data = query_db()
            except FileNotFoundError as e:
                import sys
                print(f"[ERROR] {e}", file=sys.stderr)
                self._send_json(503, {"error": str(e)})
                return
            except Exception as e:
                import sys
                print(f"[ERROR] 数据库查询失败: {e}", file=sys.stderr)
                self._send_json(500, {"error": f"数据库查询失败: {e}"})
                return
            self._send_json(200, data)
            return

        if path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "time": int(time.time())}).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode("utf-8"))

    def do_POST(self):
        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        self.send_response(404)
        self.end_headers()


def main():
    import sys
    try:
        server = http.server.ThreadingHTTPServer((HOST, PORT), TokenMonitorHandler)
    except OSError as e:
        print(f"[ERROR] 服务启动失败: {e}", file=sys.stderr)
        if "Address already in use" in str(e) or e.errno == 98:
            print(f"  端口 {PORT} 已被占用，请检查是否有其他实例在运行", file=sys.stderr)
        sys.exit(1)
    print(f"💰 小珀 Token Monitor 启动成功！（人民币计价）")
    print(f"   地址: http://{HOST}:{PORT}")
    print(f"   数据源: {DB_PATH}")
    print(f"   汇率: ¥{USD_TO_CNY}/USD")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] 收到中断信号，正在关闭...", file=sys.stderr)
        server.shutdown()


if __name__ == "__main__":
    main()
