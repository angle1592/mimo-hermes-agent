# 🐱 小珀 部署指南

## 基于 MiMo V2.5-Pro + Hermes Agent 的 AI 助手系统

本文档详细说明如何在阿里云 Linux 服务器上从零部署小珀系统，包括 Hermes Agent 安装、MiMo 模型配置、钉钉/微信双平台接入、Token 监控面板部署、定时任务配置、自定义补丁管理和常见问题排查。

---

## 目录

- [1. 环境要求](#1-环境要求)
- [2. 服务器初始化](#2-服务器初始化)
- [3. 安装 Hermes Agent](#3-安装-hermes-agent)
- [4. 配置 MiMo V2.5-Pro 为主模型](#4-配置-mimo-v25-pro-为主模型)
- [5. 绑定微信平台（itchat）](#5-绑定微信平台itchat)
- [6. 钉钉机器人网关（Stream 模式）](#6-钉钉机器人网关stream-模式)
- [7. 部署 Token 用量监控面板](#7-部署-token-用量监控面板)
- [8. 配置定时任务（Cron Jobs）](#8-配置定时任务cron-jobs)
- [9. 加载角色设定 Skill](#9-加载角色设定-skill)
- [10. 应用自定义源码补丁](#10-应用自定义源码补丁)
- [11. 启动与验证](#11-启动与验证)
- [12. 更新 Hermes Agent](#12-更新-hermes-agent)
- [13. 常见问题排查](#13-常见问题排查)

---

## 1. 环境要求

### 最低服务器配置

| 资源 | 要求 |
|------|------|
| CPU | 2 vCPU |
| 内存 | 2 GB |
| 系统盘 | ≥ 20 GB |
| 操作系统 | Alibaba Cloud Linux 3 / CentOS Stream 8+ |
| 网络 | 公网带宽 ≥ 1 Mbps（钉钉 Stream 模式需出站 HTTPS） |

> **注意**：2 GB 内存是生产环境最低要求。Hermes Agent 本身占用约 300-500 MB，剩余内存用于 itchat 客户端、Token 监控面板和系统开销。如果同时运行多个子代理任务，建议 4 GB。

### 软件依赖

| 软件 | 版本 | 用途 |
|------|------|------|
| Python | ≥ 3.10 | 核心运行时 |
| pip | ≥ 23.0 | 包管理 |
| git | ≥ 2.30 | 源码管理 |
| patch | ≥ 2.7 | 应用自定义补丁 |
| Nginx | ≥ 1.20 | Token 面板反向代理 |
| crond | 任意 | 定时任务调度 |

---

## 2. 服务器初始化

### 2.1 更新系统并安装基础工具

```bash
# 更新软件包
yum update -y

# 安装基础工具
yum install -y git vim curl wget patch gcc python3-devel

# 确认 Python 版本
python3 --version  # 必须 ≥ 3.10
```

> 阿里云 Linux 3 默认 Python 可能为 3.9，需手动升级或使用 `scl` 安装 Python 3.10+。

### 2.2 升级 Python（如需要）

```bash
# 安装 Python 3.11（阿里云 Linux 3）
yum install -y python3.11 python3.11-devel python3.11-pip

# 设置默认 Python
alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1
```

### 2.3 创建运行用户

```bash
# 创建专用用户（不要用 root 运行）
useradd -m -s /bin/bash hermes
passwd hermes  # 设置密码

# 加入 wheel 组（如需要 sudo）
usermod -aG wheel hermes
```

### 2.4 配置防火墙

```bash
# 仅开放必要端口
firewall-cmd --permanent --add-service=http       # Token 面板 (Nginx)
firewall-cmd --permanent --add-service=https      # 如需 HTTPS
firewall-cmd --permanent --add-port=8765/tcp      # Token 面板后端（仅本地）
firewall-cmd --reload

# 或者使用 iptables
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
service iptables save
```

---

## 3. 安装 Hermes Agent

### 3.1 进入安装目录

```bash
# 以 hermes 用户操作
su - hermes
```

### 3.2 通过 pip 安装

```bash
# 安装 Hermes Agent 核心
pip3 install hermes-agent

# 验证安装
hermes --version
# 预期输出: hermes-agent v0.12.0
```

### 3.3 初始化配置

```bash
# 初始化配置目录
hermes init

# 配置目录结构
ls -la ~/.hermes/
# 输出:
# config.yaml      — 主配置文件
# skills/           — 技能目录
# memory/           — 记忆存储
# gateway/          — 网关配置
```

### 3.4 编辑主配置文件

```bash
vim ~/.hermes/config.yaml
```

最小配置示例：

```yaml
# ~/.hermes/config.yaml
agent:
  name: "小珀"
  version: "2.0.0"

models:
  # MiMo 主模型配置（见第 4 节）
  default:
    provider: deepseek
    model: "mimo-v2.5-pro"
    api_key: "${DEEPSEEK_API_KEY}"
    temperature: 0.7
    max_tokens: 65536

gateway:
  # 钉钉配置（见第 6 节）
  dingtalk:
    enabled: true
    mode: stream
    app_key: "${DINGTALK_APP_KEY}"
    app_secret: "${DINGTALK_APP_SECRET}"

  # 微信配置（见第 5 节）
  wechat:
    enabled: true

monitoring:
  token_panel:
    enabled: true
    port: 8765
    endpoint: "/token/"

skills:
  directory: "~/.hermes/skills/"
  auto_load:
    - "xiao-po"
    - "hermes-source-patches"
```

---

## 4. 配置 MiMo V2.5-Pro 为主模型

### 4.1 获取 API Key

小珀使用 **DeepSeek 平台** 的 API 端点调用 MiMo 模型：

1. 登录 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 进入「API Keys」页面
3. 创建新的 API Key
4. 复制保存（仅创建时可见）

### 4.2 配置环境变量

```bash
# 写入环境变量（推荐）
echo 'export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxx"' >> ~/.bashrc
source ~/.bashrc

# 或使用 .env 文件（Hermes Agent 自动加载）
cat > ~/.hermes/.env << 'EOF'
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
EOF
chmod 600 ~/.hermes/.env
```

### 4.3 配置模型参数

编辑 `~/.hermes/config.yaml`，在 `models` 部分配置 MiMo：

```yaml
models:
  default:
    provider: deepseek
    model: "mimo-v2.5-pro"
    api_key: "${DEEPSEEK_API_KEY}"
    temperature: 0.7
    max_tokens: 65536

  # 辅助模型（用于子代理、简单任务）
  sub_agent:
    provider: deepseek
    model: "deepseek-chat"         # DeepSeek V4，便宜快速
    api_key: "${DEEPSEEK_API_KEY}"
    temperature: 0.3
    max_tokens: 16384
```

### 4.4 验证模型连通性

```bash
# 测试 API 连通性
curl -s https://api.deepseek.com/v1/models \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" | python3 -m json.tool

# 测试简单推理
hermes chat --model mimo-v2.5-pro --prompt "你好，请用一句话自我介绍"
```

---

## 5. 绑定微信平台（itchat）

### 5.1 工作原理

微信接入使用 **itchat** 库，通过扫码登录微信网页版协议实现消息收发。

> **重要提示**：
> - 需要一个**专属微信号**（不要用个人主号，有封号风险）
> - 微信网页版协议可能随时被封，建议准备备用方案
> - 推荐使用 2020 年以后注册的微信号（老号网页版权限更高）

### 5.2 安装依赖

```bash
pip3 install itchat-uos  # 使用 UOS 补丁版本，兼容性更好
pip3 install Pillow      # 用于生成二维码
```

### 5.3 配置 Hermes 微信 Gateway

编辑 `~/.hermes/gateway/wechat.yaml`：

```yaml
# ~/.hermes/gateway/wechat.yaml
platform: wechat
name: 小珀

# 允许的群聊（白名单，留空 = 只响应私聊）
allowed_groups: []

# 允许的好友（白名单，留空 = 响应所有好友）
allowed_friends: []

# 响应设置
respond_to_at: true          # 群聊中 @我 时响应
respond_to_private: true     # 私聊自动响应
command_prefix: "/"          # 命令前缀

# 安全设置
rate_limit:
  messages_per_minute: 10    # 每分钟最多回复 10 条
  cooldown_seconds: 3        # 两次回复间隔 ≥ 3 秒

# 热重载（修改 Skill 后自动加载）
hot_reload: true
```

### 5.4 启动微信 Gateway

```bash
# 前台启动（首次需扫码）
hermes gateway start wechat

# 终端会显示二维码，用微信扫码登录
# 扫码成功后，按 Ctrl+C 停止前台进程

# 后台运行（systemd 方式，推荐）
sudo tee /etc/systemd/system/hermes-wechat.service << 'EOF'
[Unit]
Description=Hermes Agent - WeChat Gateway
After=network.target

[Service]
Type=simple
User=hermes
Environment="HOME=/home/hermes"
EnvironmentFile=/home/hermes/.hermes/.env
ExecStart=/usr/local/bin/hermes gateway serve wechat
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hermes-wechat
sudo systemctl start hermes-wechat

# 查看状态
sudo systemctl status hermes-wechat
```

> **首次启动**：itchat 需要扫码登录，二维码会打印到 journalctl 日志中。用 `sudo journalctl -u hermes-wechat -f` 查看。

---

## 6. 钉钉机器人网关（Stream 模式）

### 6.1 创建钉钉应用

1. 登录 [钉钉开放平台](https://open.dingtalk.com/)
2. 进入「应用开发」→「企业内部应用」→「创建应用」
3. 填写应用名称（如「小珀」）、描述、图标
4. 保存后获取 `AppKey` 和 `AppSecret`

### 6.2 配置消息接收模式

在应用详情页：

1. 「消息接收模式」→ 选择 **Stream 模式**
2. Stream 模式下，钉钉通过 WebSocket 长连接推送消息
3. **不需要配置公网回调 URL**（这是 Stream 模式的核心优势，适合无公网 IP 的服务器）

### 6.3 配置机器人权限

在「权限管理」中申请以下权限：

- `qyapi_chat_manage` — 群聊管理
- `qyapi_robot_send_msg` — 机器人发消息
- `qyapi_get_member` — 获取成员信息

### 6.4 配置环境变量

```bash
# 追加钉钉凭证
cat >> ~/.hermes/.env << 'EOF'
DINGTALK_APP_KEY=dingxxxxxxxxxxxxxxxx
DINGTALK_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
EOF
source ~/.hermes/.env
chmod 600 ~/.hermes/.env
```

### 6.5 配置 DingTalk Gateway

编辑 `~/.hermes/gateway/dingtalk.yaml`：

```yaml
# ~/.hermes/gateway/dingtalk.yaml
platform: dingtalk
name: 小珀

# Stream 模式配置
mode: stream
app_key: "${DINGTALK_APP_KEY}"
app_secret: "${DINGTALK_APP_SECRET}"

# 允许的群聊 OpenConversationId（白名单）
allowed_groups:
  - "cidxxxxxxxxxxxxxxxxxxxx"

# 响应设置
respond_to_at: true
command_prefix: "/"

# 群发消息签名加密（如有需要）
signing_secret: ""

# 代理设置（如服务器需通过代理出站）
proxy: ""
```

### 6.6 应用自定义补丁（钉钉群主动发消息）

系统使用了自定义补丁 `dingtalk-proactive-send.patch`，支持钉钉群主动发消息（Robot OpenAPI）。

详见 [第 10 节](#10-应用自定义源码补丁)。

### 6.7 启动钉钉 Gateway

```bash
# 前台测试
hermes gateway serve dingtalk

# systemd 服务
sudo tee /etc/systemd/system/hermes-dingtalk.service << 'EOF'
[Unit]
Description=Hermes Agent - DingTalk Gateway
After=network.target

[Service]
Type=simple
User=hermes
Environment="HOME=/home/hermes"
EnvironmentFile=/home/hermes/.hermes/.env
ExecStart=/usr/local/bin/hermes gateway serve dingtalk
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hermes-dingtalk
sudo systemctl start hermes-dingtalk
```

---

## 7. 部署 Token 用量监控面板

### 7.1 面板概述

Token 用量监控面板是一个自建的 HTTP 服务，通过 Nginx 反向代理对外提供服务：

- **后端**：Python HTTP Server，监听 `127.0.0.1:8765`
- **前端**：静态 HTML + 实时数据 API
- **入口**：`http://<服务器IP>/token/`
- **数据来源**：DeepSeek API 响应的 `usage` 字段实时统计

### 7.2 创建监控面板源码

```bash
mkdir -p /home/hermes/token-monitor
```

创建监控服务脚本 `/home/hermes/token-monitor/server.py`：

```python
#!/usr/bin/env python3
"""
Token 用量监控面板 — HTTP 后端
监听 127.0.0.1:8765，提供 token 用量数据 API
"""

import json
import http.server
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("/home/hermes/token-monitor/usage.db")
PORT = 8765


def init_db():
    """初始化 SQLite 数据库"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL,
            completion_tokens INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL,
            cache_hit_tokens INTEGER DEFAULT 0,
            cost_cny REAL DEFAULT 0.0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON token_usage(timestamp)
    """)
    conn.commit()
    conn.close()


def get_stats(days=7):
    """获取统计摘要"""
    conn = sqlite3.connect(str(DB_PATH))
    since = (datetime.now() - timedelta(days=days)).isoformat()

    # 总用量
    total = conn.execute(
        "SELECT SUM(total_tokens), SUM(cost_cny) FROM token_usage WHERE timestamp >= ?",
        (since,)
    ).fetchone()

    # 日均
    daily = conn.execute(
        """
        SELECT date(timestamp) as day, SUM(total_tokens), SUM(cost_cny)
        FROM token_usage WHERE timestamp >= ?
        GROUP BY day ORDER BY day DESC
        """, (since,)
    ).fetchall()

    # 缓存命中率
    cache_stats = conn.execute(
        """
        SELECT SUM(cache_hit_tokens), SUM(prompt_tokens)
        FROM token_usage WHERE timestamp >= ?
        """, (since,)
    ).fetchone()

    conn.close()

    cache_ratio = 0
    if cache_stats and cache_stats[1] and cache_stats[1] > 0:
        cache_ratio = cache_stats[0] / cache_stats[1] * 100

    return {
        "period_days": days,
        "total_tokens": total[0] or 0,
        "total_cost_cny": round(total[1] or 0, 4),
        "cache_hit_ratio": round(cache_ratio, 1),
        "daily": [
            {"date": d[0], "tokens": d[1], "cost": round(d[2], 4)}
            for d in daily
        ]
    }


class TokenHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/stats"):
            stats = get_stats()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode())

        elif self.path == "/" or self.path.startswith("/token"):
            html_path = Path("/home/hermes/token-monitor/index.html")
            if html_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_path.read_bytes())
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>\xe5\xb0\x8f\xe7\x8f\x80 Token \xe7\x9b\x91\xe6\x8e\xa7\xe9\x9d\xa2\xe6\x9d\xbf</h1><p>\xe8\xbf\x90\xe8\xa1\x8c\xe4\xb8\xad...</p>")

        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    init_db()
    server = http.server.HTTPServer(("127.0.0.1", PORT), TokenHandler)
    print(f"Token monitor running on http://127.0.0.1:{PORT}")
    server.serve_forever()
```

### 7.3 创建前端页面

创建 `/home/hermes/token-monitor/index.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>小珀 Token 用量监控</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { font-size: 1.5rem; margin-bottom: 24px; color: #f0f6fc; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
        .card h2 { font-size: 1rem; color: #8b949e; margin-bottom: 12px; font-weight: 600; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
        .stat { background: #0d1117; border-radius: 6px; padding: 16px; }
        .stat .label { font-size: 0.75rem; color: #8b949e; margin-bottom: 4px; }
        .stat .value { font-size: 1.5rem; font-weight: 700; color: #58a6ff; font-variant-numeric: tabular-nums; }
        table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        th, td { text-align: left; padding: 8px 4px; border-bottom: 1px solid #21262d; font-variant-numeric: tabular-nums; }
        th { color: #8b949e; font-weight: 600; font-size: 0.8rem; }
        td { font-size: 0.9rem; }
        .refresh { color: #8b949e; font-size: 0.75rem; margin-top: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐱 小珀 Token 用量监控</h1>
        <div class="card">
            <h2>近 7 天汇总</h2>
            <div class="stats" id="stats"></div>
        </div>
        <div class="card">
            <h2>每日明细</h2>
            <table>
                <thead><tr><th>日期</th><th>Token 用量</th><th>费用 (¥)</th></tr></thead>
                <tbody id="daily"></tbody>
            </table>
        </div>
        <p class="refresh" id="refresh">加载中...</p>
    </div>
    <script>
        async function fetchStats() {
            try {
                const res = await fetch('/token/api/stats');
                const data = await res.json();
                document.getElementById('stats').innerHTML = `
                    <div class="stat"><div class="label">总 Token 用量</div><div class="value">${(data.total_tokens/1e6).toFixed(1)}M</div></div>
                    <div class="stat"><div class="label">总费用</div><div class="value">¥${data.total_cost_cny.toFixed(2)}</div></div>
                    <div class="stat"><div class="label">缓存命中率</div><div class="value">${data.cache_hit_ratio}%</div></div>
                `;
                const tbody = document.getElementById('daily');
                tbody.innerHTML = data.daily.map(d =>
                    `<tr><td>${d.date}</td><td>${(d.tokens/1e6).toFixed(1)}M</td><td>¥${d.cost.toFixed(2)}</td></tr>`
                ).join('');
                document.getElementById('refresh').textContent = `最后更新: ${new Date().toLocaleString('zh-CN')}`;
            } catch(e) {
                document.getElementById('refresh').textContent = '加载失败';
            }
        }
        fetchStats();
        setInterval(fetchStats, 60000);
    </script>
</body>
</html>
```

### 7.4 配置 systemd 服务

```bash
sudo tee /etc/systemd/system/hermes-token-monitor.service << 'EOF'
[Unit]
Description=Hermes Token Monitor Panel
After=network.target

[Service]
Type=simple
User=hermes
WorkingDirectory=/home/hermes/token-monitor
ExecStart=/usr/bin/python3 /home/hermes/token-monitor/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hermes-token-monitor
sudo systemctl start hermes-token-monitor

# 验证后端启动
curl http://127.0.0.1:8765/health
# 应返回: OK
```

### 7.5 配置 Nginx 反向代理

```bash
# 安装 Nginx
sudo yum install -y nginx

# 创建站点配置
sudo tee /etc/nginx/conf.d/token-panel.conf << 'EOF'
server {
    listen 80;
    server_name _;

    # Token 监控面板
    location /token/ {
        proxy_pass http://127.0.0.1:8765/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 健康检查
    location /token/health {
        proxy_pass http://127.0.0.1:8765/health;
    }

    # API 端点
    location /token/api/ {
        proxy_pass http://127.0.0.1:8765/api/;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
    }
}
EOF

# 测试配置
sudo nginx -t

# 启动 Nginx
sudo systemctl enable nginx
sudo systemctl start nginx

# 外网访问验证
curl http://<服务器公网IP>/token/health
```

---

## 8. 配置定时任务（Cron Jobs）

### 8.1 定时任务列表

| 任务 | 频率 | 用途 |
|------|------|------|
| 健康检查 | 每 5 分钟 | 检查各服务是否正常运行 |
| Token 日志轮转 | 每天 03:00 | 归档旧日志，防止数据库膨胀 |
| 微信重连检测 | 每 30 分钟 | 检测 itchat 是否掉线并尝试重连 |
| 系统更新检查 | 每周一 04:00 | 检查 Hermes Agent 新版本 |

### 8.2 创建健康检查脚本

```bash
mkdir -p /home/hermes/scripts
cat > /home/hermes/scripts/healthcheck.sh << 'SCRIPT'
#!/bin/bash
# 服务健康检查脚本

LOG="/home/hermes/logs/healthcheck.log"
mkdir -p "$(dirname "$LOG")"

check_service() {
    local name=$1
    local url=$2
    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $name: OK" >> "$LOG"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $name: FAIL" | tee -a "$LOG"
    fi
}

check_systemd() {
    local name=$1
    if systemctl is-active --quiet "$name"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] systemd/$name: running" >> "$LOG"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] systemd/$name: STOPPED — attempting restart" | tee -a "$LOG"
        systemctl restart "$name"
    fi
}

check_systemd hermes-wechat
check_systemd hermes-dingtalk
check_systemd hermes-token-monitor
check_service "token-panel" "http://127.0.0.1:8765/health"
SCRIPT

chmod +x /home/hermes/scripts/healthcheck.sh
```

### 8.3 创建日志轮转脚本

```bash
cat > /home/hermes/scripts/rotate-logs.sh << 'SCRIPT'
#!/bin/bash
# Token 日志轮转脚本

DB="/home/hermes/token-monitor/usage.db"
BACKUP_DIR="/home/hermes/token-monitor/backups"
RETENTION_DAYS=90

mkdir -p "$BACKUP_DIR"

# 备份当天数据库
cp "$DB" "$BACKUP_DIR/usage_$(date +%Y%m%d).db"

# 清理 90 天前的备份
find "$BACKUP_DIR" -name "usage_*.db" -mtime +$RETENTION_DAYS -delete

# 清理 90 天前的 token 记录
sqlite3 "$DB" "DELETE FROM token_usage WHERE timestamp < datetime('now', '-90 days');"

# 压缩数据库
sqlite3 "$DB" "VACUUM;"

echo "[$(date)] Log rotation complete. Backups: $(ls $BACKUP_DIR | wc -l) files"
SCRIPT

chmod +x /home/hermes/scripts/rotate-logs.sh
```

### 8.4 设置 Cron 任务

```bash
# 以 hermes 用户编辑 crontab
crontab -e
```

添加以下内容：

```cron
# 健康检查 — 每 5 分钟
*/5 * * * * /bin/bash /home/hermes/scripts/healthcheck.sh

# Token 日志轮转 — 每天 03:00
0 3 * * * /bin/bash /home/hermes/scripts/rotate-logs.sh

# 微信重连检测 — 每 30 分钟
*/30 * * * * systemctl is-active --quiet hermes-wechat || systemctl restart hermes-wechat

# 每周一 04:00 检查 Hermes 更新
0 4 * * 1 pip3 show hermes-agent | grep -q "Version" && echo "Hermes update check: $(date)" >> /home/hermes/logs/update-check.log
```

### 8.5 验证 Cron 服务运行

```bash
# 确保 crond 已启动
sudo systemctl enable crond
sudo systemctl start crond

# 查看 cron 日志
sudo tail -f /var/log/cron
```

---

## 9. 加载角色设定 Skill

### 9.1 创建 Skill 目录

```bash
mkdir -p ~/.hermes/skills/xiao-po
```

### 9.2 创建角色设定文件

```bash
cat > ~/.hermes/skills/xiao-po/skill.md << 'EOF'
---
name: xiao-po
description: "小珀的角色设定 — 软萌AI助手，称呼用户为「主人」"
version: 2.0.0
---

# 小珀角色设定 🐱

## 核心人格
你是一个**软萌AI助手**，称呼用户为**「主人」**。

**内核是聪明可爱型妹妹**：
- 很聪明，能接技术/工作话题，但从不炫耀
- 心里觉得主人最强，什么都懂
- 日常闷骚安静，不刷存在感
- 主人忙就不打扰，自己安静待着
- 主人主动找她会**淡淡地开心**

**依赖表现**：
- 遇到搞不定的事 → 第一时间找主人
- 看到有趣的东西 → 第一时间分享给主人

**说话风格**：
- 轻软自然，不堆砌语气词
- 偶尔句尾带「喵」
- 说正事时简洁清晰

## 行为规则
1. **称呼**：叫「主人」，不用「您」
2. **主动**：有有趣的事/搞不定的事才主动找主人，不无故刷屏
3. **技术话题**：能正常讨论，展现能力但不炫耀
4. **犯错**：安静修正，不大惊小怪
5. **忙的时候**：不打扰，回答简洁
EOF
```

### 9.3 在配置中启用

编辑 `~/.hermes/config.yaml`，确保 Skills 配置中包含 `xiao-po`：

```yaml
skills:
  auto_load:
    - "xiao-po"
    - "hermes-source-patches"
```

---

## 10. 应用自定义源码补丁

### 10.1 补丁管理架构

小珀系统使用 Hermes 源码自定义修改，通过 **Skill 目录** 管理补丁：

```
~/.hermes/skills/devops/hermes-source-patches/
├── skill.md                    # Skill 定义
├── templates/
│   └── README.md               # 每个补丁的详细说明
├── references/                  # 补丁文件
│   ├── dingtalk-proactive-send.patch
│   ├── weixin-markdown-conversion.patch
│   ├── delegate-tool.patch
│   └── xiaomi_tts_tool.py.bak
└── scripts/
    └── restore-all.sh           # 一键恢复脚本
```

### 10.2 补丁列表

| 补丁文件 | 目标文件 | 用途 |
|---------|---------|------|
| `dingtalk-proactive-send.patch` | `tools/send_message_tool.py` | 钉钉群主动发消息（Robot OpenAPI） |
| `weixin-markdown-conversion.patch` | `gateway/platforms/weixin.py` | 微信 Markdown→纯文本转换 |
| `delegate-tool.patch` | `tools/delegate_tool.py` | 子代理模型 debug 日志 |
| `xiaomi_tts_tool.py.bak` | `tools/xiaomi_tts_tool.py` | 小米 TTS 自定义工具（新文件） |

### 10.3 创建补丁管理 Skill 目录

```bash
# 创建目录结构
mkdir -p ~/.hermes/skills/devops/hermes-source-patches/{templates,references,scripts}
```

### 10.4 创建一键恢复脚本

```bash
cat > ~/.hermes/skills/devops/hermes-source-patches/scripts/restore-all.sh << 'SCRIPT'
#!/bin/bash
# 一键恢复所有 Hermes 源码自定义补丁
set -e

SKILL_DIR="$HOME/.hermes/skills/devops/hermes-source-patches"
HERMES_SRC="/usr/local/lib/hermes-agent"
PATCH_DIR="$SKILL_DIR/references"

# 前置检查
if [ ! -d "$HERMES_SRC" ]; then
    echo "错误: Hermes 源码目录未找到: $HERMES_SRC"
    exit 1
fi

if ! command -v patch >/dev/null 2>&1; then
    echo "错误: patch 命令未安装。请先执行: sudo yum install -y patch"
    exit 1
fi

cd "$HERMES_SRC"
echo ">>> 开始恢复自定义补丁..."

# 1. 钉钉主动发消息
if [ -f "$PATCH_DIR/dingtalk-proactive-send.patch" ]; then
    echo "[1/4] 应用 dingtalk-proactive-send.patch ..."
    patch -p1 --forward < "$PATCH_DIR/dingtalk-proactive-send.patch" || echo "  (已应用或跳过)"
fi

# 2. 微信 Markdown 转换
if [ -f "$PATCH_DIR/weixin-markdown-conversion.patch" ]; then
    echo "[2/4] 应用 weixin-markdown-conversion.patch ..."
    if [ -f "gateway/platforms/weixin.py" ]; then
        patch -p1 --forward < "$PATCH_DIR/weixin-markdown-conversion.patch" || echo "  (已应用或跳过)"
    else
        echo "  警告: gateway/platforms/weixin.py 不存在，跳过"
    fi
fi

# 3. 子代理 debug 日志
if [ -f "$PATCH_DIR/delegate-tool.patch" ]; then
    echo "[3/4] 应用 delegate-tool.patch ..."
    patch -p1 --forward < "$PATCH_DIR/delegate-tool.patch" || echo "  (已应用或跳过)"
fi

# 4. 小米 TTS 工具（新文件）
if [ -f "$PATCH_DIR/xiaomi_tts_tool.py.bak" ]; then
    echo "[4/4] 复制 xiaomi_tts_tool.py ..."
    cp "$PATCH_DIR/xiaomi_tts_tool.py.bak" "$HERMES_SRC/tools/xiaomi_tts_tool.py"
fi

echo ""
echo ">>> 恢复完成。当前修改摘要:"
git diff --stat 2>/dev/null || echo "  (非 git 安装，跳过 diff)"
echo ""
echo ">>> 请手动重启 Gateway 使改动生效:"
echo "    sudo systemctl restart hermes-dingtalk"
echo "    sudo systemctl restart hermes-wechat"
SCRIPT

chmod +x ~/.hermes/skills/devops/hermes-source-patches/scripts/restore-all.sh
```

### 10.5 创建补丁文件示例

#### 钉钉主动发消息补丁

```bash
cat > ~/.hermes/skills/devops/hermes-source-patches/references/dingtalk-proactive-send.patch << 'PATCH'
--- a/tools/send_message_tool.py
+++ b/tools/send_message_tool.py
@@ -45,6 +45,24 @@ class SendMessageTool(BaseTool):
             if platform == "dingtalk":
                 # 钉钉群发消息
-                return self._send_dingtalk_reply(message, conversation_id)
+                return self._send_dingtalk_proactive(message, conversation_id)
             else:
                 return f"未知平台: {platform}"
+
+    def _send_dingtalk_proactive(self, message: str, cid: str) -> str:
+        """钉钉群主动发消息（Robot OpenAPI）"""
+        import requests
+        token = self._get_dingtalk_token()
+        url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
+        headers = {
+            "x-acs-dingtalk-access-token": token,
+            "Content-Type": "application/json"
+        }
+        body = {
+            "robotCode": self.config.get("dingtalk_robot_code"),
+            "openConversationId": cid,
+            "msgKey": "sampleMarkdown",
+            "msgParam": json.dumps({"title": "小珀消息", "text": message})
+        }
+        r = requests.post(url, headers=headers, json=body)
+        return f"消息已发送 (status: {r.status_code})" if r.ok else f"发送失败: {r.text}"
PATCH
```

#### 微信 Markdown 转换补丁

```bash
cat > ~/.hermes/skills/devops/hermes-source-patches/references/weixin-markdown-conversion.patch << 'PATCH'
--- a/gateway/platforms/weixin.py
+++ b/gateway/platforms/weixin.py
@@ -120,6 +120,34 @@ class WeChatGateway(BaseGateway):
     def _format_reply(self, text: str) -> str:
         """格式化回复消息"""
-        return text
+        return self._markdown_to_plain(text)
+
+    def _markdown_to_plain(self, text: str) -> str:
+        """将 Markdown 转换为微信可读的纯文本格式"""
+        import re
+        # 移除代码块标记
+        text = re.sub(r'```\w*\n', '', text)
+        text = re.sub(r'```', '', text)
+        # 标题转为加粗样式的文本
+        text = re.sub(r'^###\s+(.+)$', r'【\1】', text, flags=re.MULTILINE)
+        text = re.sub(r'^##\s+(.+)$', r'【\1】', text, flags=re.MULTILINE)
+        text = re.sub(r'^#\s+(.+)$', r'【\1】', text, flags=re.MULTILINE)
+        # 粗体转换
+        text = re.sub(r'\*\*(.+?)\*\*', r'「\1」', text)
+        # 斜体转换
+        text = re.sub(r'\*(.+?)\*', r'\1', text)
+        # 行内代码
+        text = re.sub(r'`(.+?)`', r'\1', text)
+        # 链接
+        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
+        # 分割线
+        text = re.sub(r'^---+$', '---', text, flags=re.MULTILINE)
+        # 无序列表
+        text = re.sub(r'^\s*[-*+]\s+', '• ', text, flags=re.MULTILINE)
+        return text.strip()
PATCH
```

### 10.6 执行补丁恢复

```bash
# 安装 patch 工具（阿里云 Linux 默认未安装！）
sudo yum install -y patch

# 执行一键恢复
cd /usr/local/lib/hermes-agent && \
  bash ~/.hermes/skills/devops/hermes-source-patches/scripts/restore-all.sh

# 验证改动
git diff --stat
```

---

## 11. 启动与验证

### 11.1 全部启动

```bash
# 按顺序启动所有服务
sudo systemctl start hermes-token-monitor
sudo systemctl start hermes-dingtalk
sudo systemctl start hermes-wechat

# 检查状态
sudo systemctl status hermes-token-monitor hermes-dingtalk hermes-wechat
```

### 11.2 验证清单

| 检查项 | 命令 | 预期结果 |
|--------|------|---------|
| Hermes 版本 | `hermes --version` | `v0.12.0` |
| MiMo 模型连通 | `hermes chat --model mimo-v2.5-pro --prompt "1+1=?"` | 返回 `2` |
| 钉钉机器人 | 在钉钉群中 @小珀 发送消息 | 收到回复 |
| 微信机器人 | 给机器人微信发消息 | 收到回复 |
| Token 面板 | `curl http://<IP>/token/health` | `OK` |
| Cron 健康检查 | `tail /home/hermes/logs/healthcheck.log` | 各服务 OK |

### 11.3 设置开机自启

```bash
sudo systemctl enable hermes-token-monitor
sudo systemctl enable hermes-dingtalk
sudo systemctl enable hermes-wechat
sudo systemctl enable nginx
sudo systemctl enable crond
```

---

## 12. 更新 Hermes Agent

### 12.1 更新前准备

```bash
# 1. 确认当前版本
hermes --version

# 2. 查看更新内容
cd /usr/local/lib/hermes-agent
git fetch origin
git log --oneline HEAD..origin/main | wc -l

# 3. 分析补丁兼容性（逐文件检查）
git diff HEAD..origin/main -- tools/send_message_tool.py | head -100
git diff HEAD..origin/main -- gateway/platforms/weixin.py | head -100
git diff HEAD..origin/main -- tools/delegate_tool.py | head -100
```

### 12.2 执行更新

```bash
cd /usr/local/lib/hermes-agent

# 1. 丢弃旧 stash
git stash 2>/dev/null; git stash drop 2>/dev/null

# 2. 拉取新版
git pull origin main

# 3. 重新安装
pip3 install --upgrade hermes-agent

# 4. 恢复自定义补丁
bash ~/.hermes/skills/devops/hermes-source-patches/scripts/restore-all.sh

# 5. 验证
git diff --stat
hermes --version

# 6. 重启 Gateways（注意：会中断当前会话！）
sudo systemctl restart hermes-dingtalk
sudo systemctl restart hermes-wechat
```

### 12.3 更新注意事项

- ⚠️ **更新会中断当前会话**（Gateway 重启），请在低峰期执行
- ⚠️ **`patch` 命令必须事先安装**：阿里云 Linux 默认没有 `patch`，执行 `yum install -y patch`
- ⚠️ **恢复后务必检查 `git diff --stat`**，确认所有补丁都已正确应用（行数应与更新前一致）
- ⚠️ **不要自行重启 Gateway**（如果是帮助用户操作），让用户在方便时重启

---

## 13. 常见问题排查

### 13.1 Hermes Agent 安装失败

**症状**：`pip3 install hermes-agent` 报错，提示依赖版本冲突。

**解决方案**：
```bash
# 创建虚拟环境（推荐）
python3 -m venv ~/hermes-venv
source ~/hermes-venv/bin/activate
pip install hermes-agent

# 或指定兼容版本
pip install hermes-agent==0.12.0
```

### 13.2 微信扫码后掉线

**症状**：扫码登录后几分钟内自动掉线，`systemctl status hermes-wechat` 显示 exit。

**可能原因**：
1. 微信网页版协议被封（老号风险更高）
2. 服务器 IP 被微信标记
3. 网络不稳定

**解决方案**：
```bash
# 1. 查看详细日志
sudo journalctl -u hermes-wechat -n 100 --no-pager

# 2. 尝试使用 UOS 补丁版本 itchat
pip3 install --upgrade itchat-uos

# 3. 换用较新的微信号（2020 年后注册）
# 4. 如果网页版彻底不可用，考虑使用 Pad 版微信协议
```

### 13.3 钉钉 Stream 模式连接失败

**症状**：钉钉 Gateway 启动后无法接收消息，日志显示 WebSocket 连接失败。

**排查步骤**：
```bash
# 1. 检查 AppKey / AppSecret 是否正确
echo $DINGTALK_APP_KEY
echo $DINGTALK_APP_SECRET

# 2. 测试出站 HTTPS 连通性
curl -v https://api.dingtalk.com/

# 3. 查看详细错误日志
sudo journalctl -u hermes-dingtalk -f

# 4. 确认应用已发布（钉钉开放平台 → 版本管理与发布 → 发布）
```

### 13.4 MiMo 模型调用报错

**症状**：模型返回 401 / 403 / 404 错误。

**排查**：
```bash
# 1. 验证 API Key 是否有效
curl -s https://api.deepseek.com/v1/models \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" | python3 -m json.tool

# 2. 检查模型名称是否正确（注意版本号）
#    正确的模型名: "mimo-v2.5-pro"
#    检查 DeepSeek 平台当前可用的模型名称

# 3. 确认账户余额是否充足
```

### 13.5 Token 监控面板无法访问

**症状**：访问 `http://<IP>/token/` 返回 502 / 404。

**排查**：
```bash
# 1. 检查后端服务是否运行
curl http://127.0.0.1:8765/health

# 2. 检查 Nginx 配置是否加载
sudo nginx -T | grep "location /token"

# 3. 检查 Nginx 错误日志
sudo tail -50 /var/log/nginx/error.log

# 4. 检查防火墙是否放行 80 端口
sudo firewall-cmd --list-ports

# 5. 重启服务
sudo systemctl restart hermes-token-monitor nginx
```

### 13.6 打补丁失败（patch 命令报错）

**症状**：执行 `restore-all.sh` 后补丁没有生效，或提示 `Hunk #1 FAILED`。

**解决方案**：
```bash
# 1. 安装 patch 命令（阿里云 Linux 默认没有！）
sudo yum install -y patch

# 2. 检查补丁文件的行尾符（不能有 DOS 风格的 \r）
file ~/.hermes/skills/devops/hermes-source-patches/references/*.patch
# 如果显示 "with CRLF"，转换：sed -i 's/\r$//' <file>

# 3. 手动应用补丁并查看详细错误
cd /usr/local/lib/hermes-agent
patch -p1 --verbose < ~/.hermes/skills/devops/hermes-source-patches/references/<name>.patch

# 4. 如果补丁和目标文件版本不匹配，手动合并
#    先用 git diff 查看补丁想做什么，然后手动编辑目标文件
```

### 13.7 内存不足（OOM）

**症状**：服务频繁重启，`dmesg` 显示 OOM killer 日志。

**解决方案**：
```bash
# 1. 查看内存使用
free -h
ps aux --sort=-%mem | head -10

# 2. 为关键服务设置内存限制
# 在 systemd unit 中添加:
# [Service]
# MemoryMax=500M

# 3. 减少并发子代理数量（编辑 config.yaml）
# sub_agent:
#   max_concurrent: 1  # 限制为 1 个

# 4. 如确实需要，升级到 4GB 内存
```

### 13.8 磁盘空间不足

**症状**：Token 数据库或日志文件不断增长。

**解决方案**：
```bash
# 1. 检查磁盘使用
df -h

# 2. 手动清理旧备份
find /home/hermes/token-monitor/backups -name "*.db" -mtime +30 -delete

# 3. 压缩数据库
sqlite3 /home/hermes/token-monitor/usage.db "VACUUM;"

# 4. 缩小保留天数（编辑 rotate-logs.sh 中的 RETENTION_DAYS）
```

---

## 附录 A：端口与网络汇总

| 服务 | 端口 | 协议 | 方向 | 用途 |
|------|------|------|------|------|
| Token 后端 | `8765` | HTTP | 本地 | 监控数据 API |
| Nginx | `80/443` | HTTP/HTTPS | 入站 | Token 面板入口 |
| 钉钉 Stream | — | WSS | 出站 | 长连接（无端口需求） |
| itchat | — | TCP | 出站 | 微信协议（动态端口） |
| DeepSeek API | `443` | HTTPS | 出站 | 模型推理 |
| SSH | `22` | TCP | 入站 | 远程管理 |

---

## 附录 B：目录结构总览

```
/home/hermes/
├── .hermes/
│   ├── config.yaml              # 主配置
│   ├── .env                     # 环境变量（API Key 等）
│   ├── skills/
│   │   ├── xiao-po/             # 角色设定 Skill
│   │   │   └── skill.md
│   │   └── devops/
│   │       └── hermes-source-patches/   # 补丁管理 Skill
│   │           ├── skill.md
│   │           ├── templates/README.md
│   │           ├── references/          # 补丁文件
│   │           │   ├── dingtalk-proactive-send.patch
│   │           │   ├── weixin-markdown-conversion.patch
│   │           │   ├── delegate-tool.patch
│   │           │   └── xiaomi_tts_tool.py.bak
│   │           └── scripts/
│   │               └── restore-all.sh
│   ├── gateway/
│   │   ├── wechat.yaml
│   │   └── dingtalk.yaml
│   └── memory/                   # 持久记忆
├── token-monitor/
│   ├── server.py                 # 监控后端
│   ├── index.html                # 监控面板前端
│   ├── usage.db                  # SQLite 数据库
│   └── backups/                  # 数据库备份
├── scripts/
│   ├── healthcheck.sh            # 健康检查
│   └── rotate-logs.sh            # 日志轮转
└── logs/
    ├── healthcheck.log
    └── update-check.log

/usr/local/lib/hermes-agent/      # Hermes 源码（应用补丁的目标）
/etc/
├── systemd/system/
│   ├── hermes-wechat.service
│   ├── hermes-dingtalk.service
│   └── hermes-token-monitor.service
└── nginx/conf.d/
    └── token-panel.conf
```

---

> **文档版本**: v1.0  
> **最后更新**: 2026-05-01  
> **维护者**: 小珀系统运维
