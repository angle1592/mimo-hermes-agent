# Update Session: 2026-05-22 (826 commits, v0.13.0 → v0.14.0)

## 版本变化
- 旧: v0.13.0 (2026.5.7) `d36413211`
- 新: v0.14.0 (2026.5.16) `4e2c66a09`
- 差距: 826 commits, 252 个新文件

## 主要上游变化
- `run_agent.py`: 巨量重构 (600+/12530-)，代码拆分到 `agent/` 子模块 (`conversation_loop.py`, `system_prompt.py`, `tool_dispatch_helpers.py`, `tool_executor.py`, `iteration_budget.py` 等)
- `send_message_tool.py`: Slack DM/Thread 支持, Telegram proxy 支持, thread-not-found fallback (151+/28-)
- `delegate_tool.py`: heartbeat 线程安全修复, delegation api_mode 自动检测, custom provider 识别 (29+/6-)

## Patch 兼容性分析

| Patch | 上游改动 | 结果 |
|-------|---------|------|
| dingtalk-proactive-send.patch (line 1598) | 前 950 行大量改动 | ✅ offset +123 自动适配 |
| weixin-markdown-passthrough.patch | format_message 包装层变更 | ⚠️ Hunk #2 失败，手动修复 |
| delegate-tool.patch (line 978/1029) | line 31/1431/2358+ 改动 | ✅ offset +5 自动适配 |
| xiaomi_tts_tool.py.bak | 无改动 | ✅ 文件已存在跳过 |

## 手动修复详情: weixin.py

**问题**: `restore-all.sh` 报 `Hunk #2 FAILED at 2096`

**根因**: 上游在 `format_message()` 中新增了 `_wrap_copy_friendly_lines_for_weixin()` 包装层:
```python
# v0.13: return _normalize_markdown_blocks(content)
# v0.14: return _wrap_copy_friendly_lines_for_weixin(_normalize_markdown_blocks(content))
```

**修复**: 将内层 `_normalize_markdown_blocks(content)` 替换为 `_convert_markdown_for_weixin(content)`，保留外层包装:
```python
return _wrap_copy_friendly_lines_for_weixin(_convert_markdown_for_weixin(content))
```

**操作步骤**:
1. `cat gateway/platforms/weixin.py.rej` — 查看失败的 hunk
2. `grep -n "_normalize_markdown_blocks\|_convert_markdown_for_weixin\|def format_message" gateway/platforms/weixin.py` — 定位当前代码
3. 用 `patch` 工具做针对性替换
4. `git diff gateway/platforms/weixin.py > references/weixin-markdown-passthrough.patch` — 重新生成 patch
5. `rm -f gateway/platforms/weixin.py.rej` — 清理 reject 文件
6. `python3 -c "import py_compile; py_compile.compile('gateway/platforms/weixin.py', doraise=True)"` — 验证编译

## 验证结果
- 3 个被修改文件编译通过
- `hermes --version` 显示 v0.14.0 (2026.5.16)
