# Update Session: v0.12.0 → v0.13.0 (2026-05-15)

## Stats
- **Before**: v0.12.0 (2026.4.30)
- **After**: v0.13.0 (2026.5.7)
- **Commits**: 1006
- **Conflicts**: 2 manual fixes needed

## Patch Results

| Patch | Status | Detail |
|-------|--------|--------|
| dingtalk-proactive-send | ✅ auto | offset +285 lines |
| weixin-markdown-passthrough | ⚠️ manual fix | Hunk #1 auto (offset +62), Hunk #2 failed |
| delegate-tool | ⚠️ manual fix | Hunk #1 auto (offset +34), Hunk #2 failed |
| xiaomi_tts_tool.py.bak | ✅ no change | new file, not in upstream |

## Conflict Details

### weixin.py — format_message() pipeline changed
Upstream changed `format_message()` from:
```python
return _convert_markdown_for_weixin(content)
```
to:
```python
return _wrap_copy_friendly_lines_for_weixin(_normalize_markdown_blocks(content))
```
New function `_wrap_copy_friendly_lines_for_weixin()` (line 737) wraps long lines for easier copying in WeChat clients. Our patch replaces the entire pipeline with `return content` (raw passthrough).

**Lesson**: Upstream keeps evolving the weixin formatting pipeline. Each update may change the "before" state of `format_message()`. Always check what the current upstream code looks like before assuming the old patch context matches.

### delegate_tool.py — context mismatch
Old patch added a blank line between `effective_api_mode` assignment and `effective_acp_command`. Upstream refactored `effective_api_mode` into an if/else block (3 lines instead of 1), breaking context matching. Trivial fix — just insert the blank line at the new location.

## Post-Update Actions
- Regenerated all 3 .patch files to reflect new upstream base
- Syntax check passed on all modified files
- Gateway restart pending (user discretion)
