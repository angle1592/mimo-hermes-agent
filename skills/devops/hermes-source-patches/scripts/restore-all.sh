#!/bin/bash
# 一键恢复所有自定义修改（更新 Hermes 后运行）
# 用法: bash ~/.hermes/skills/devops/hermes-source-patches/scripts/restore-all.sh

set -e

# 依赖检查
command -v patch >/dev/null 2>&1 || { echo "❌ 需要先安装 patch: yum install -y patch"; exit 1; }

# 自动定位：以脚本所在目录为基准
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
REFS_DIR="$SKILL_DIR/references"
HERMES_DIR="/usr/local/lib/hermes-agent"

cd "$HERMES_DIR"

echo "🔧 恢复自定义修改..."
echo ""

# 1. DingTalk 主动发送
if [ -f "$REFS_DIR/dingtalk-proactive-send.patch" ]; then
    echo "📌 钉钉主动发送补丁..."
    patch -p1 --forward < "$REFS_DIR/dingtalk-proactive-send.patch" 2>/dev/null && echo "  ✅ 已应用" || echo "  ⏭️  已存在或冲突，跳过"
fi

# 2. WeChat Markdown 转换
if [ -f "$REFS_DIR/weixin-markdown-conversion.patch" ]; then
    echo "📌 微信 Markdown 转换..."
    patch -p1 --forward < "$REFS_DIR/weixin-markdown-conversion.patch" 2>/dev/null && echo "  ✅ 已应用" || echo "  ⏭️  已存在或冲突，跳过"
fi

# 3. Delegate tool 修改
if [ -f "$REFS_DIR/delegate-tool.patch" ]; then
    echo "📌 子代理工具修改..."
    patch -p1 --forward < "$REFS_DIR/delegate-tool.patch" 2>/dev/null && echo "  ✅ 已应用" || echo "  ⏭️  已存在或冲突，跳过"
fi

# 4. Xiaomi TTS 自定义工具（新文件）
if [ -f "$REFS_DIR/xiaomi_tts_tool.py.bak" ]; then
    echo "📌 小米 TTS 工具..."
    if [ ! -f "$HERMES_DIR/tools/xiaomi_tts_tool.py" ]; then
        cp "$REFS_DIR/xiaomi_tts_tool.py.bak" "$HERMES_DIR/tools/xiaomi_tts_tool.py"
        echo "  ✅ 已恢复"
    else
        echo "  ⏭️  文件已存在，跳过（如需覆盖请手动 cp）"
    fi
fi

# 清理 pycache
echo ""
echo "🧹 清理 __pycache__..."
find "$HERMES_DIR" -name "__pycache__" -path "*/gateway/*" -exec rm -rf {} + 2>/dev/null || true
find "$HERMES_DIR" -name "__pycache__" -path "*/tools/*" -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "✅ 恢复完成！请重启 Gateway: hermes gateway restart"
