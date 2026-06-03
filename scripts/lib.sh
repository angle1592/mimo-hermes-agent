#!/usr/bin/env bash
# lib.sh — Shared shell utilities for mimo-hermes-agent scripts
#
# Usage: source "$(dirname "$0")/lib.sh"

# ── Colors ─────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ── Logging ────────────────────────────────────────────
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
log()   { echo "[$(basename "$0")] $(date '+%H:%M:%S') $*"; }

# ── Common checks ──────────────────────────────────────
require_root() {
    if [[ $EUID -ne 0 ]]; then
        error "请用 root 运行此脚本"
    fi
}

check_swap() {
    if ! swapon --show | grep -q .; then
        warn "No swap detected. On <=2GB RAM machines, heavy operations may crash."
        warn "See docs/shared/china-infra-patterns.md 'Swap Setup' for instructions."
    fi
}

# ── Sanitization ───────────────────────────────────────
# Redact sensitive patterns from a file in-place
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
        -e 's/(client_id:\s*).*/\1REDACTED/' \
        -e 's/(client_secret:\s*).*/\1REDACTED/' \
        -e 's/(record_key:\s*).*/\1FILL_IN/' \
        "$file"
}
