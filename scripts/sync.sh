#!/usr/bin/env bash
# sync.sh — 自动同步 Hermes Agent 配置和文档到 GitHub 仓库
set -euo pipefail

REPO_DIR="/root/mimo-hermes-agent"
HERMES_DIR="${HERMES_DIR:-$HOME/.hermes}"
DRY_RUN="${1:-}"

log() { echo "[sync] $(date '+%H:%M:%S') $*"; }

# 自定义 skill 白名单
CUSTOM_SKILLS=(
    "xiao-po"
    "hermes-token-monitor"
    "yuanbao"
    "dogfood"
    "research/wechat-article-reader"
    "devops/hermes-source-patches"
    "devops/china-github-mirror"
    "devops/deploy-service-china"
    "gateway/weixin-setup"
    "gateway/hermes-dingtalk-setup"
    "software-development/import-external-skill"
    "autonomous-ai-agents/hermes-agent"
)

# 脱敏函数：处理单个文件
sanitize_file() {
    local file="$1"
    sed -i -E \
        -e 's/cid[A-Za-z0-9+/=]{10,}/REDACTED_CHAT_ID/g' \
        -e 's/47\.119\.146\.[0-9]+/YOUR_SERVER_IP/g' \
        -e 's/ghp_[A-Za-z0-9]+/REDACTED_PAT/g' \
        -e 's/sk-[A-Za-z0-9]{20,}/REDACTED_KEY/g' \
        -e 's/(chat_id:\s*).*/\1REDACTED/' \
        -e 's/(app_key:\s*).*/\1REDACTED/' \
        -e 's/(app_secret:\s*).*/\1REDACTED/' \
        -e 's/(api_key:\s*).*/\1""/' \
        -e 's/(client_secret:\s*).*/\1REDACTED/' \
        -e 's/(record_key:\s*).*/\1FILL_IN/' \
        "$file"
}

sync_config() {
    log "同步 config.yaml..."
    local src="$HERMES_DIR/config.yaml"
    local dst="$REPO_DIR/config/config.yaml.example"
    [ -f "$src" ] || { log "  跳过"; return; }
    cp "$src" "$dst"
    sanitize_file "$dst"
    log "  → config/config.yaml.example"
}

sync_skills() {
    log "同步自定义 skills..."
    rm -rf "$REPO_DIR/skills"
    mkdir -p "$REPO_DIR/skills"
    for skill_path in "${CUSTOM_SKILLS[@]}"; do
        local src="$HERMES_DIR/skills/$skill_path"
        local dst="$REPO_DIR/skills/$skill_path"
        if [ ! -d "$src" ]; then
            log "  跳过: $skill_path"
            continue
        fi
        mkdir -p "$dst"
        cp -r "$src"/* "$dst/"
        log "  → skills/$skill_path/"
    done
}

sync_token_monitor() {
    log "同步 token_monitor..."
    local src="$HERMES_DIR/token_monitor/server.py"
    [ -f "$src" ] || { log "  跳过"; return; }
    cp "$src" "$REPO_DIR/scripts/token_monitor.py"
    log "  → scripts/token_monitor.py"
}

sync_soul() {
    log "同步 SOUL.md..."
    local src="$HERMES_DIR/SOUL.md"
    [ -f "$src" ] || { log "  跳过"; return; }
    cp "$src" "$REPO_DIR/docs/SOUL.md"
    log "  → docs/SOUL.md"
}

sync_cron_jobs() {
    log "同步 cron jobs..."
    local src="$HERMES_DIR/cron/jobs.json"
    [ -f "$src" ] || { log "  跳过"; return; }
    local dst="$REPO_DIR/docs/cron-jobs.md"
    cat > "$dst" << 'HEADER'
# Cron Jobs 配置

> 自动生成，勿手动编辑。运行 `bash scripts/sync.sh` 更新。

| 状态 | 名称 | 调度 | 说明 |
|------|------|------|------|
HEADER
    python3 -c "
import json
with open('$src') as f:
    jobs = json.load(f)
for job in jobs:
    name = job.get('name', job.get('id', 'unnamed'))
    schedule = job.get('schedule', 'N/A')
    enabled = job.get('enabled', True)
    prompt = job.get('prompt', '')
    desc = prompt.split('。')[0][:80] if prompt else ''
    if len(prompt.split('。')[0]) > 80:
        desc += '...'
    status = '✅' if enabled else '⏸️'
    print(f'| {status} | {name} | \`{schedule}\` | {desc} |')
" >> "$dst" 2>/dev/null || echo "| ❌ | - | - | 解析失败 |" >> "$dst"
    log "  → docs/cron-jobs.md"
}

# 全局脱敏扫描
sanitize_all() {
    log "全局脱敏扫描..."
    local count=0
    while IFS= read -r -d "" file; do
        if grep -qE 'cid[A-Za-z0-9+/=]{10,}|47\.119\.146\.[0-9]+|ghp_[A-Za-z0-9]+|sk-[A-Za-z0-9]{20,}' "$file" 2>/dev/null; then
            sanitize_file "$file"
            count=$((count + 1))
            log "  脱敏: ${file#$REPO_DIR/}"
        fi
    done < <(find "$REPO_DIR" -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.py" -o -name "*.sh" \) -print0)
    log "  扫描完成，处理了 $count 个文件"
}

update_readme_date() {
    local readme="$REPO_DIR/README.md"
    sed -i "s/截至 [0-9]\{4\} 年 [0-9]\{1,2\} 月/截至 $(date '+%Y 年 %-m 月')/g" "$readme" 2>/dev/null || true
}

main() {
    log "开始同步: $HERMES_DIR → $REPO_DIR"

    sync_config
    sync_skills
    sync_token_monitor
    sync_soul
    sync_cron_jobs
    sanitize_all
    update_readme_date

    cd "$REPO_DIR"
    git add -A

    if git diff --cached --quiet; then
        log "没有变更，跳过提交"
    else
        local file_count
        file_count=$(git diff --cached --name-only | wc -l)
        log "变更: $file_count 个文件"

        if [ "$DRY_RUN" = "--dry-run" ]; then
            log "[DRY RUN] 会提交以下文件:"
            git diff --cached --name-only
            git reset HEAD -- . >/dev/null 2>&1
        else
            git commit -m "sync: auto-update $(date '+%Y-%m-%d %H:%M')"
            git push origin main 2>&1 || {
                local branch
                branch=$(git rev-parse --abbrev-ref HEAD)
                git push origin "$branch" 2>&1
            }
            log "同步完成 ✅"
        fi
    fi
}

main "$@"
