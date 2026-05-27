# Update Session: 2026-05-24

## Summary
- **From:** v0.13.0 (commit 4e2c66a09) → **To:** v0.14.0 (commit bb4703c76, tag v2026.5.16)
- **Commits:** 409
- **Mirror:** `git pull https://githubfast.com/NousResearch/hermes-agent.git main`

## Pre-update Analysis

| Patch file | Upstream changes | Risk |
|------------|-----------------|------|
| dingtalk-proactive-send.patch | 255 lines deleted (Discord funcs moved to plugin), but patch targets `_send_dingtalk` which upstream didn't touch | Low ✅ |
| weixin-markdown-passthrough.patch | 2 lines added (`filter_media_delivery_paths`) in different area | Low ✅ |
| delegate-tool.patch | No upstream changes | None ✅ |
| xiaomi_tts_tool.py.bak | No upstream changes (new file) | None ✅ |

## Patch Results

| Patch | Status | Notes |
|-------|--------|-------|
| dingtalk-proactive-send | ✅ auto | Offset -114 lines (upstream deleted Discord functions above) |
| weixin-markdown-passthrough hunk 1 | ✅ auto | Offset +62 lines |
| weixin-markdown-passthrough hunk 2 | ❌ FAILED | Manual fix needed (see below) |
| delegate-tool | ✅ auto | Offset +5 lines |
| xiaomi_tts_tool.py | ⏭️ exists | No action needed |

## Manual Fix: weixin hunk 2

**Root cause:** Upstream added `_wrap_copy_friendly_lines_for_weixin()` as outer wrapper in `format_message`:
```python
# Old (what patch expected):
return _normalize_markdown_blocks(content)

# New (upstream v0.14.0):
return _wrap_copy_friendly_lines_for_weixin(_normalize_markdown_blocks(content))
```

**Fix:** Replace only the inner function, keep the wrapper:
```python
return _wrap_copy_friendly_lines_for_weixin(_convert_markdown_for_weixin(content))
```

**Steps:**
1. `cat gateway/platforms/weixin.py.rej` — see what failed
2. `grep -n "_normalize_markdown_blocks" gateway/platforms/weixin.py` — find current location (line 2192)
3. `sed -n '2188,2198p'` — confirm surrounding context
4. `patch` tool to replace the expression
5. `git diff gateway/platforms/weixin.py > references/weixin-markdown-passthrough.patch` — regenerate patch
6. `rm -f gateway/platforms/weixin.py.rej` — cleanup

## Post-update Verification
- `git diff --stat` → 3 files, 196 insertions, 7 deletions (matches pre-update)
- `python3 -c "import py_compile; ..."` → all 3 files pass
- `hermes --version` → v0.14.0 (2026.5.16)

## Pitfalls Encountered
- None unexpected. The weixin wrapper addition was the only surprise.
