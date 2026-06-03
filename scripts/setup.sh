#!/bin/bash
# Hermes Agent 国内环境快速部署脚本
# 用法: bash setup.sh
# 
# 此脚本会：
#   1. 安装基础依赖
#   2. 安装 Hermes Agent
#   3. 部署 Token 监控面板
#   4. 配置 Nginx 反代
#   5. 创建 systemd 服务
#
# 前提条件：
#   - 阿里云 Linux 3+ / CentOS Stream 8+ / 其他 RHEL 系
#   - root 权限
#   - 已有模型 API Key（DeepSeek 或 MiMo）

set -euo pipefail

# Load shared utilities (colors, logging, common checks)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

# ── 检查 root ─────────────────────────────────────────
require_root

# ── 1. 安装依赖 ───────────────────────────────────────
info "安装基础依赖..."
if command -v yum &>/dev/null; then
    yum install -y python3 python3-pip git curl wget nginx patch gcc python3-devel || error "yum 安装失败，请检查网络或软件源配置"
elif command -v apt-get &>/dev/null; then
    apt-get update && apt-get install -y python3 python3-pip git curl wget nginx patch gcc python3-dev || error "apt-get 安装失败，请检查网络或软件源配置"
else
    error "未找到 yum 或 apt-get，请手动安装依赖"
fi

# 确认 Python 版本
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [[ $(echo "$PY_VER < 3.10" | bc) -eq 1 ]]; then
    warn "Python 版本 $PY_VER 低于 3.10，可能有兼容问题"
fi

# ── 2. 安装 Hermes Agent ──────────────────────────────
info "安装 Hermes Agent..."
pip3 install hermes-agent 2>&1 || {
    warn "pip3 install 失败，尝试 --break-system-packages..."
    pip3 install --break-system-packages hermes-agent || error "Hermes Agent 安装失败"
}

# 初始化
hermes --version || error "Hermes 安装失败"
info "Hermes 版本: $(hermes --version)"

# 初始化配置目录
hermes init 2>&1 || warn "hermes init 返回非零状态（可能已初始化过）"

# ── 3. 部署 Token 监控面板 ────────────────────────────
info "部署 Token 监控面板..."
MONITOR_DIR="$HOME/.hermes/token_monitor"
mkdir -p "$MONITOR_DIR"

# 复制监控脚本
if [[ -f "scripts/token_monitor.py" ]]; then
    cp scripts/token_monitor.py "$MONITOR_DIR/server.py"
else
    warn "未找到 scripts/token_monitor.py，请手动复制"
fi

# ── 4. 配置 systemd 服务 ─────────────────────────────
info "配置 systemd 服务..."

# Token Monitor
if [[ -f "deploy/systemd/hermes-token-monitor.service" ]]; then
    cp deploy/systemd/hermes-token-monitor.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable hermes-token-monitor
    info "Token 监控服务已配置"
fi

# Dashboard
if [[ -f "deploy/systemd/hermes-dashboard.service" ]]; then
    cp deploy/systemd/hermes-dashboard.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable hermes-dashboard
    info "Dashboard 服务已配置"
fi

# ── 5. 配置 Nginx ─────────────────────────────────────
info "配置 Nginx..."
if [[ -f "deploy/nginx/hermes.conf" ]]; then
    cp deploy/nginx/hermes.conf /etc/nginx/conf.d/hermes.conf
    nginx -t && systemctl enable nginx && systemctl restart nginx
    info "Nginx 配置完成"
else
    warn "未找到 Nginx 配置文件"
fi

# ── 6. 启动服务 ───────────────────────────────────────
info "启动服务..."
systemctl start hermes-token-monitor 2>&1 || warn "Token 监控启动失败，请检查: systemctl status hermes-token-monitor"
systemctl start hermes-dashboard 2>&1 || warn "Dashboard 启动失败，请检查: systemctl status hermes-dashboard"

# ── 完成 ──────────────────────────────────────────────
echo ""
info "========================================="
info "  部署完成！"
info "========================================="
echo ""
echo "接下来需要手动完成："
echo "  1. 配置模型 API Key:"
echo "     hermes config set model.default <model-name>"
echo "     编辑 ~/.hermes/.env 添加 API Key"
echo ""
echo "  2. 配置消息平台（钉钉/微信）："
echo "     参考 docs/deployment-guide.md"
echo ""
echo "  3. 启动 Hermes Gateway："
echo "     hermes gateway start"
echo ""
echo "  4. 访问面板："
echo "     Token 监控: http://<你的IP>/token/"
echo "     Dashboard:  http://<你的IP>/"
echo ""
