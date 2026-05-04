# Filesystem Cleanup Audit

When the user reports messy files or wants to clean up the home directory. Run this audit to categorize what's junk, what's valuable, and what needs user decision.

## Audit Commands

```bash
# 1. Home directory overview
ls -la /root/

# 2. Find scattered test/temp files
find /root -maxdepth 2 \( -name "*test*" -o -name "*tmp*" -o -name "*.bak" -o -name "*debug*" \) \
  -not -path '*.hermes/skills*' -not -path '*node_modules*' -not -path '*.git*' -not -path '*__pycache__*'

# 3. Large cache directories
du -sh ~/.cache/*/ 2>/dev/null
du -sh ~/.hermes/checkpoints/ 2>/dev/null
du -sh ~/.hermes/sessions/ 2>/dev/null

# 4. One-off scripts and scraped files
ls /root/*.html /root/*.js /root/*.json /root/*.py 2>/dev/null

# 5. npm/node artifacts outside of project dirs
ls /root/package*.json /root/node_modules 2>/dev/null

# 6. Old config backups
ls ~/.hermes/*.bak* 2>/dev/null
```

## Typical Junk Categories

| Category | Examples | Safe to Delete |
|----------|----------|---------------|
| Scraped HTML docs | *.html from API research | ✅ After research is done |
| Scraping scripts | scrape_*.js, puppeteer configs | ✅ After scraping is done |
| Test outputs | text_*.json, debug_*.py | ✅ |
| npm artifacts | node_modules/, package*.json in home root | ✅ If not needed |
| Old config backups | config.yaml.bak.* | ⚠️ Ask user |
| Puppeteer Chromium | ~/.cache/puppeteer/ (600MB+) | ✅ If Playwright MCP is used instead |

## Cache That Should NOT Be Deleted

| Cache | Why |
|-------|-----|
| ~/.cache/ms-playwright/ | Playwright MCP browser — needed for browser automation |
| ~/.cache/pip/ | Speeds up Python installs |
| ~/.cache/uv/ | Speeds up uv installs |
| ~/.hermes/sessions/ | Session history (FTS5 searchable) |

## Checkpoints (~/.hermes/checkpoints/)

Hermes checkpoints are git-based snapshots of conversation state. They can be very large (800MB+). Cleaning them loses the ability to restore old conversation context, but does NOT affect the memory system or skills.

```bash
# Check checkpoint sizes
du -sh ~/.hermes/checkpoints/*/

# If user wants to clean:
rm -rf ~/.hermes/checkpoints/<id>
```

## Prevention: File Placement Convention

User-established convention to keep the home directory clean:

- **Temp/scratch files** → `/tmp/hermes-work/` (mkdir -p if needed, delete when done)
- **Long-term scripts** → `~/.hermes/scripts/` or the relevant skill's `scripts/` directory
- **Home root** → NEVER place temp files, scraped HTML, debug scripts, or test outputs here
- **Project files** → each in its own directory (e.g., `~/mimo-hermes-agent/`)

Create the temp directory at the start of any scraping/research task:
```bash
mkdir -p /tmp/hermes-work
```

## Post-Cleanup Verification

After cleaning:
- df -h — confirm space freed
- hermes gateway status — confirm nothing broke
- Test a cron job if any were related to cleaned files
