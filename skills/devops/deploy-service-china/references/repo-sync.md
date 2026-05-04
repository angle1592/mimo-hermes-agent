# GitHub Repo Auto-Sync Pattern

Automatically sync Hermes Agent config, skills, and docs to a GitHub repo as a persistent knowledge base.

## Architecture

```
~/.hermes/ (source)  →  sync.sh  →  ~/mimo-hermes-agent/ (git repo)  →  GitHub
```

## Sync Script Template

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/root/mimo-hermes-agent"  # HARDCODE, don't use relative paths
HERMES_DIR="${HERMES_DIR:-$HOME/.hermes}"

# Whitelist of custom skills (don't sync all system skills)
CUSTOM_SKILLS=(
    "xiao-po"
    "hermes-token-monitor"
    "research/wechat-article-reader"
    # ... add your custom skills
)

# Sanitize a single file
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
        "$file"
}

# Global scan AFTER sync (catches leaks in skill examples, docs, etc.)
sanitize_all() {
    while IFS= read -r -d "" file; do
        if grep -qE 'cid[A-Za-z0-9+/=]{10,}|ghp_[A-Za-z0-9]+|sk-[A-Za-z0-9]{20,}' "$file" 2>/dev/null; then
            sanitize_file "$file"
        fi
    done < <(find "$REPO_DIR" -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.py" -o -name "*.sh" \) -print0)
}
```

## What to Sync

| Content | Source | Destination |
|---------|--------|-------------|
| Config (sanitized) | `~/.hermes/config.yaml` | `config/config.yaml.example` |
| Custom skills | `~/.hermes/skills/<whitelist>` | `skills/` |
| Token monitor | `~/.hermes/token_monitor/server.py` | `scripts/` |
| SOUL.md | `~/.hermes/SOUL.md` | `docs/` |
| Cron jobs overview | `~/.hermes/cron/jobs.json` | `docs/cron-jobs.md` |

## What NOT to Sync

- `.env` (API keys)
- `auth.json` (auth tokens)
- Session data, caches, databases, logs
- System-provided skills (huge, not customized)

## Git Mirror Setup (China servers)

```bash
# insteadOf rewrites github.com → mirror transparently
git config --global url."https://githubfast.com/".insteadOf "https://github.com/"

# Credentials for BOTH hosts (git looks up rewritten host)
echo "https://USER:TOKEN@github.com" > ~/.git-credentials
echo "https://USER:TOKEN@githubfast.com" >> ~/.git-credentials
git config --global credential.helper store
chmod 600 ~/.git-credentials

# Remote uses clean github.com URL (rewritten by insteadOf)
git remote set-url origin https://github.com/owner/repo.git
```

## Pitfalls

- **REPO_DIR must be hardcoded** — if script lives at `~/.hermes/scripts/sync.sh`, `$(dirname "$0")/..` points to `~/.hermes/`, NOT the repo. Use absolute path.
- **sed escaping is fragile in dynamically generated scripts** — Python writing shell scripts with sed -E and regex has terrible escaping. Safer to `cp` file first, then `sed -i` in place.
- **Privacy leaks hide in skill example files** — DingTalk chat IDs in example `--deliver` flags, server IPs in deployment docs. ALWAYS run global scan after sync, don't just sanitize config.
- **git push --dry-run first** — verify credentials work before setting up cron.
- **Cron job cwd may be deleted** — if a cron job's working directory gets removed, subsequent terminal calls fail with `FileNotFoundError: No such file or directory`. Terminal sessions inherit CWD, so once it's deleted, ALL terminal calls fail (including `read_file` in some contexts). **Workaround:** use `execute_code` with `os.chdir('/root')` or use `workdir` parameter. If that also fails, the session CWD is permanently stuck — inform user and switch to a fresh execution context.
