# Automated Repo Sync: Local Hermes Config → GitHub

Pattern for keeping a GitHub repo in sync with local `~/.hermes/` configuration and custom skills. Inspired by the "洁癖.skill" concept — persistent documentation that survives session resets.

## What to Sync

| Source | Destination | Sanitization |
|--------|-------------|-------------|
| `~/.hermes/config.yaml` | `config/config.yaml.example` | Strip `api_key`, `client_secret`, `record_key` values |
| Custom skills (whitelist) | `skills/<category>/<name>/` | None (skills don't contain secrets) |
| `~/.hermes/token_monitor/server.py` | `scripts/token_monitor.py` | None |
| `~/.hermes/SOUL.md` | `docs/SOUL.md` | None |
| `~/.hermes/cron/jobs.json` | `docs/cron-jobs.md` | Truncate prompts, auto-generate markdown table |

## What NOT to Sync

- `.env` — API keys, secrets
- `auth.json` — authentication tokens
- `sessions/`, `cache/`, `state.db` — runtime state
- `logs/` — transient
- System-provided skills (hundreds of files, not user-created)

## Custom Skill Whitelist

Don't sync everything — system skills (comfyui, powerpoint, etc.) are huge and not user-created. Maintain an explicit whitelist in the sync script:

```bash
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
```

Update this list when new custom skills are created.

## Config Sanitization

```bash
sed -E \
    -e 's/(api_key:\s*).+/\1""/' \
    -e 's/(client_secret:\s*).+/\1"REDACTED"/' \
    -e 's/(record_key:\s*).+/\1"FILL_IN"/' \
    "$src" > "$dst"
```

Always review the diff before first push to ensure no secrets leaked.

## Git Push via Mirror (China)

On servers using `git config --global url."https://githubfast.com/".insteadOf "https://github.com/"`:

1. Remote URL should use `github.com` (insteadOf rewrites transparently)
2. Credentials in `~/.git-credentials` need entries for **both** `github.com` AND the mirror host (`githubfast.com`), because git looks up credentials for the rewritten URL
3. Test with `git push --dry-run origin main` before enabling cron

## Cron Schedule

Every 6 hours is a good default — frequent enough to catch changes, not so frequent it wastes resources:

```
0 */6 * * *
```

The sync script should be idempotent (safe to run multiple times). If no changes, skip commit.

## Script Location

Store at `~/.hermes/scripts/repo-sync.sh` (long-term scripts directory). The script should:
- Use a hardcoded `REPO_DIR` (not relative to script location, which may change)
- Pull latest before syncing (to avoid conflicts)
- Only commit+push if there are actual changes
- Log with timestamps for debugging
