# Hermes update session: v0.18.0 to v0.18.2

Date: 2026-07-14

## Result

- Updated from Hermes Agent v0.18.0 to v0.18.2.
- Upstream advanced by 1008 commits.
- Git checkout finished aligned with `origin/main`.
- Official updater completed dependency installation successfully.
- `hermes doctor` ended with `All checks passed`.

## Network handling

The first attempt failed during Git fetch because the connection to GitHub was interrupted. Before retrying, mihomo was changed to a US-first automatic fallback group. The successful retry exported `HTTP_PROXY` and `HTTPS_PROXY` as `http://127.0.0.1:7890` for the updater.

## Transactional rollback improvement

The first update script restored the Dashboard after failure but did not restore source patches that had already been cleaned. The retry script treated source state and service state as one transaction:

1. Save the full source diff and config backup.
2. Stop Dashboard to release memory.
3. Clean tracked source customizations.
4. Run the official updater through mihomo.
5. On success or failure, restore missing patches, remove `.orig`/`.rej`, run `py_compile`, and verify all six patches with reverse apply checks.
6. Start Dashboard only after patch validation.

See `references/update-failure-transactional-rollback.md` for the reusable failure pattern.

## Patch compatibility

All active patches applied without rejection on upstream `226e8de8`:

- DingTalk proactive send
- Weixin Markdown passthrough
- Weixin dedup race fix
- Delegate model debug log
- Custom-provider reasoning support in `run_agent.py`
- Custom-provider reasoning support in `chat_completions.py`

Post-update diff stayed at five files with 288 insertions/deletions in the expected shape. All patched Python files compiled successfully and all six patch files passed reverse-apply verification.

## Runtime verification

- Dashboard systemd service active.
- Dashboard local HTTP endpoint healthy.
- DingTalk, Weixin, and Telegram all connected; Gateway reported three running platforms.
- Main provider smoke test returned HTTP 200 with expected content.
- Subagent smoke test dispatched separately and should be verified from its returned result and `agent.log` model/provider entry.
