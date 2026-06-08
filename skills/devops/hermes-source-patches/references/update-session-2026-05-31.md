# Update Session: v0.16.0 → v0.16.0 (12 commits fast-forward)

**Date:** 2026-05-31
**From:** v0.16.0 (2a10da3a, 2026.6.5 build)
**To:** v0.16.0 (8e223b36e)
**Commits:** 12
**Method:** `git pull origin main` (fast-forward)
**Patch conflicts:** None

## Commits Analysis

12 commits, all CLI refactoring and ACP/memory fixes:

| Commit | Area | Files |
|--------|------|-------|
| 8e223b36e | curator: protect built-in skills | agent/curator.py, tools/skill_usage.py |
| 777dc9da6 | ACP: session provenance metadata | acp_adapter/provenance.py, server.py |
| 240c5d454 | chore: AUTHOR_MAP | scripts/release.py |
| 132d6fe6d | volcengine: strip XML fragments | agent/agent_runtime_helpers.py |
| f5bd09af4 | ACP: interrupt-sentinel refactor | acp_adapter/server.py, agent/conversation_loop.py |
| 9b631e4ae | ACP: suppress cancel sentinel | acp_adapter/server.py |
| 2789bf4e2 | auxiliary: Codex Responses converter | agent/auxiliary_client.py |
| 568e12761 | CLI: extract 25 subcommand parsers | hermes_cli/main.py → subcommands/ |
| 4da45e872 | CLI: extract profile+gateway parsers | hermes_cli/main.py → subcommands/ |
| b2e605324 | CLI: extract cron parser | hermes_cli/main.py → subcommands/ |
| 54870847c | agent: extract turn_context.py | agent/conversation_loop.py → turn_context.py |
| 86c537d20 | memory: in-turn consolidation retry | tools/memory_tool.py |

**Zero commits touched our patched files** (weixin.py, delegate_tool.py, send_message_tool.py).

## Key Technique: Per-Commit File Overlap Check

Before pulling, checked each commit's changed files to verify no overlap with patched files:

```bash
cd /usr/local/lib/hermes-agent
for commit in $(git log --format='%H' HEAD..origin/main); do
  echo "=== $(git log --oneline -1 $commit) ==="
  git diff --name-only $commit~1 $commit 2>/dev/null
done
```

This gives per-commit granularity (better than `git diff HEAD..origin/main -- <file>` for large gaps) and immediately shows whether any patch files are in the blast zone.

## Result

- Fast-forward merge, no conflicts
- `pip install -e .` succeeded (croniter-6.2.2, openai-2.33.0 updated)
- All 3 patches survived intact (verified with grep)
- `.orig` files from patch detection needed cleanup: `rm -f <file>.orig`
- `hermes --version` showed "12 commits behind" even though HEAD == origin/main (known pitfall, display issue with upstream tracking ref)
