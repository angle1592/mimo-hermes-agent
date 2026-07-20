# Hermes update session — 2026-07-20

## Scope

Updated a heavily customized Hermes checkout from `226e8de82` to upstream `7f12d4f89` (975 commits total across the update window) on a 2 GB RAM server.

## Durable lessons

### 1. Test patches in an isolated worktree first

Create a detached worktree at the fetched upstream tip, apply every patch there, and inspect both apply status and runtime behavior. Five patches initially applied; the old `run_agent.py` reasoning patch conflicted.

### 2. Prefer upstream configuration/profile support over rewriting a patch

The conflicting reasoning patch was not rewritten blindly. Tracing the new provider path showed `CustomProfile.build_api_kwargs_extras()` now emits `reasoning_effort` as a top-level API argument. Verified:

- main profile effort `high`
- delegation profile effort `xhigh`
- live `shayulajiao` API request returned `OK`

Therefore both historical reasoning source patches were retired from `restore-all.sh` rather than adapted.

### 3. Low-memory update pattern

The dashboard and its duplicate MCP children held about 870 MB swap. Stop the dashboard while keeping the separately managed Gateway alive, then add a temporary 2 GB swapfile for the dependency-install window. Do not assume the historical process topology; inspect systemd units first.

### 4. Use a controlled manual update when automatic restart would sever the session

Safe sequence used:

1. Back up `config.yaml`, `.env`, HEAD, status, diff, and stash list.
2. Stash local source changes.
3. `git pull --ff-only origin main`.
4. Reinstall editable dependencies with the discovered `uv` executable.
5. Run `restore-all.sh` after retiring obsolete patches.
6. Remove `.orig`/`.rej` artifacts.
7. Validate syntax, `git diff --check`, expected diff stat, targeted tests, config, doctor, and live model request.
8. Fetch again immediately before finalization; upstream advanced by three commits during the run, so those were pulled and patches re-applied.
9. Confirm `hermes update --check` says already up to date at that point.
10. Restart from a PID-1-owned transient systemd timer because two Hermes one-shot cron attempts were removed without executing their scripts. Verify the new Gateway process and Dashboard independently.

### 7. Do not rely on an in-Gateway Hermes cron to restart the Gateway

Two `no_agent=true` one-shot jobs were scheduled from the running Gateway. Both disappeared from the job list without executing the restart script or creating its log; one only recorded a Weixin delivery rate-limit error. The successful path was:

```bash
systemd-run --unit=hermes-post-update-restart --on-active=15s /root/hermes-post-update-restart.sh
```

This creates a transient timer owned by systemd PID 1, fully outside the Gateway process tree. The Gateway and Dashboard then restarted successfully. For future self-restarts, prefer a PID-1-owned transient unit when Hermes cron execution itself is under test or stale.

## Final verification

Final installed commit: `7f12d4f8907f3f022653ad1250992e1d5362caed` (`975` commits after the pre-update `226e8de82`).

Verified after restart:

- Gateway active with a new process and current source
- Weixin current conversation handled by the new Gateway
- Dashboard `/` and `/health` returned HTTP 200
- DingTalk proactive Robot OpenAPI send returned `success: true`
- Delegation smoke test returned exact `SUBAGENT_OK`
- Runtime logs showed `provider=custom`, `base_url=https://shayulajiao.xyz/v1`, `model=gpt-5.6-sol`
- Live custom-provider request with `reasoning_effort=high` returned `OK`
- Targeted upstream suite: `228 passed`
- `hermes doctor`: all checks passed
- Custom patch syntax and `git diff --check`: passed

Upstream advanced another 20 commits after completion. These are recorded as post-update upstream movement, not a failed update; do not chase a continuously moving `main` indefinitely in one maintenance window.

The temporary 2 GB update swapfile was retained because it was actively carrying about 1.5 GB after Dashboard and Gateway startup. Removing it then would risk memory pressure on the 2 GB server. Remove only after swap usage has migrated or fallen safely.

### 5. Patch apply success is insufficient

The Weixin patch applied with offset and fuzz. Validation included reading the actual landing region and behavior probes:

- Markdown heading/table/bold conversion
- same body with different message IDs enters the queue only once
- DingTalk upstream tests
- custom-provider request argument tests

Targeted upstream suite result: 228 passed.

### 6. Update status can change during a long run

`HEAD == origin/main` only proves alignment with the last fetch. Run `hermes update --check` or fetch again just before declaring completion. Distinguish a stale tracking ref from upstream genuinely advancing.

## Files retained as active patches

- DingTalk proactive send
- Weixin Markdown conversion/passthrough
- Weixin duplicate-message race fix
- Delegate child-model debug log

## Retired patches

- `reasoning-effort-custom-provider-run-agent.patch`
- `reasoning-effort-custom-provider-chat-completions.patch`

The files may remain as historical references, but the restore script must not apply them.