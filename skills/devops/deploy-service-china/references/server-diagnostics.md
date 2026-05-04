# Server Diagnostics: After Unresponsive/Hang Incident

Use when: server was unresponsive, SSH hung, disk I/O maxed out, or user reports a crash/hard reboot.

## Quick Triage Sequence

Run these in parallel — they give the full picture fast:

```bash
# 1. Disk usage + I/O stats + recent kernel messages
df -h && echo "===" && iostat -x 1 2 2>/dev/null | tail -20 && echo "===" && dmesg -T 2>/dev/null | tail -30

# 2. Recent warnings/errors from journal
journalctl --since "1 hour ago" --no-pager -p warning 2>/dev/null | tail -40

# 3. Current resource snapshot
top -b -n1 | head -20
```

## Check for Unclean Shutdown

```bash
# Journal corruption = unclean shutdown
# Look for "corrupted or uncleanly shut down" in dmesg
dmesg | grep -i "corrupted\|uncleanly"

# Compare boot times — if uptime is much shorter than expected, there was a reboot
uptime -s
```

## Investigate Previous Boot (Before Crash)

```bash
# Errors from the boot BEFORE the crash
journalctl -b -1 --no-pager -p err 2>/dev/null | tail -20

# Last entries before crash (narrow the time window)
journalctl -b -1 --no-pager --since "YYYY-MM-DD HH:MM" 2>/dev/null | tail -30

# Check for OOM killer
dmesg | grep -i "oom\|out of memory\|killed process"
```

## Common Causes on 2C2G Machines

| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| SSH hangs, disk I/O maxed, no OOM log | Memory exhaustion without swap (kernel hangs, can't even OOM) | Check if swap existed at crash time |
| OOM kill messages in dmesg | Process consumed too much RAM | `dmesg \| grep oom` — find which process |
| Journal corrupted, clean reboot | User forced reboot | Ask user if they rebooted |
| Random reboot with no journal gap | Cloud provider maintenance | Check Alibaba Cloud console for notifications |
| Single service crashed but system OK | Application bug | `journalctl -u SERVICE -b 0` |

## Pitfall: No Swap = Silent Hang

On 2GB machines with no swap, heavy memory usage (pip install, npm install, Hermes updates) can cause the kernel to freeze without triggering OOM killer. The system just stops responding. There are NO useful logs because the kernel can't write them.

**Always verify swap is active:**
```bash
swapon --show
# If empty → no swap → add it immediately (see SKILL.md Step 0)
```

## Pitfall: Corrupted Journal = Forced Reboot

If `systemd-journald` reports "file corrupted or uncleanly shut down", the previous shutdown was NOT clean. This means:
- The logs from the crash moment are likely lost (not flushed to disk)
- Check the LAST entries in the previous boot journal (`journalctl -b -1`) for the last activity before hang
- The gap between last journal entry and the reboot time tells you when the hang started

## Check for Hermes-Related Crash Cause

If Hermes is installed, check its own logs for the crash window:

```bash
# Hermes update log (shows if an update was running)
cat ~/.hermes/logs/update.log | tail -30
cat ~/.hermes/logs/hermes-update.log | tail -30

# General hermes logs
tail -50 ~/.hermes/logs/agent.log
tail -50 ~/.hermes/logs/errors.log
```

**Pattern:** If `update.log` shows a large update (100+ commits) with dependency reinstalls, and the crash happened shortly after → update overwhelmed RAM/disk on a low-spec machine.

## Post-Recovery Checklist

After diagnosing and recovering from a crash:

1. **Verify swap exists** — `swapon --show`. If empty, add it immediately.
2. **Check cron jobs** — `hermes cron list`. Jobs scheduled during the downtime window were likely missed. Manually trigger them: `hermes cron run <job_id>`.
3. **Verify core services** — `systemctl status hermes-gateway nginx` etc.
4. **Check disk space** — `df -h`. Crash recovery can leave temp files.
