# Update Session: 2026-05-05 (302 commits)

## Context
- **From:** v0.12.0 (2026.4.30), commit f99676e31
- **To:** 601e5f1d5 (302 commits, latest on main)
- **Mirror:** githubfast.com (China server)

## Upstream Changes Affecting Patched Files
| File | Upstream Changes | Our Patch | Result |
|------|-----------------|-----------|--------|
| `gateway/platforms/weixin.py` | Content-fingerprint dedup (L1333), send_weixin_direct loop fix (L2037) | Markdown passthrough at L2121 → L2128 (+12 offset) | ✅ No conflict |
| `tools/send_message_tool.py` | Feishu media support (L589), QQBot C2C/group (L1670), imports (L10) | Dingtalk proactive send at L1313 → L1491 (+178 offset) | ✅ No conflict |
| `tools/delegate_tool.py` | Heartbeat thresholds (L483), fallback_chain inheritance (L1026), credential resolution (L2230) | Debug logging at L944, L985 | ✅ No conflict |
| `run_agent.py` | IterationBudget lock (L304), OpenRouter cache (L1258), init-time fallback (L1473), review budget bump (L3578) | None (only config workaround) | ✅ N/A |

## Patch Results
- dingtalk-proactive-send: offset 178 lines
- weixin-markdown-passthrough: offset 12 lines (hunk 1), 32 lines (hunk 2)
- delegate-tool: applied directly (no offset)
- xiaomi_tts_tool: skipped (file already exists, no change needed)

## Notable New Features (302 commits)
- Microsoft Teams platform adapter
- video_analyze tool (native video understanding)
- Telegram DM topic mode (/topic)
- Kanban multi-project boards
- Cron no_agent mode (script-only jobs)
- OpenRouter response caching
- Docker dashboard side-process (HERMES_DASHBOARD=1)
- Nous OAuth cross-profile sharing
- Weixin content-fingerprint dedup

## Post-Update Quirk
`hermes --version` still showed "302 commits behind" because we pulled from githubfast.com mirror, not origin. The version check compares against `origin/main` ref. Code is actually at latest — `git log --oneline -1` confirms HEAD = 601e5f1d5. User was told to run `hermes gateway restart` when convenient.
