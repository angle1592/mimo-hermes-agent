# 更新会话 2026-08-18：v0.18.0 → v0.20.3 (2026.8.16.2)

## 概况

- 更新跨度：2324 commits（origin/main 计数为准，首次 fetch 只更新 FETCH_HEAD 有偏差）
- 变更规模：928 files changed, +76862/-8101
- 版本：v0.18.0 (2026.7.1) → v0.20.3 (2026.8.16.2)，Python 3.11.6 → 3.11.15

## 更新前准备

- swap 已耗尽（可用仅 107MB），先加临时 swap 2G（`/swapfile-update`）再更新，完成后 swapoff + 删除。发现已有 `/swapfile-hermes-update`（2G，此前遗留），保留。
- 基线记录：更新前 `git diff --stat` = 3 files, 251 insertions(+), 11 deletions(-)

## 补丁恢复结果

restore-all.sh 因脚本内含 "hermes gateway restart" 字样被安全机制拦截（gateway 进程内禁止重启类脚本），改为手动逐个 patch 应用：

| Patch | 结果 |
|-------|------|
| dingtalk-proactive-send.patch | ✅ Hunk #1 offset 56 行 |
| weixin-markdown-passthrough.patch | ✅ 3 hunks，offset 18/48/48 行 |
| weixin-dedup-race-fix.patch | ✅ Reversed/previously applied — 已被 passthrough 补丁包含（代码确认存在） |
| delegate-tool.patch | ✅ Hunk #1 offset 274 行 |

验证：
- `git diff --stat` 与更新前基线完全一致（3 files, 251 insertions, 11 deletions）
- py_compile 三个被修改文件全部通过
- weixin patch 引用的 `_convert_markdown_for_weixin` / `_rewrite_table_block_for_weixin` / `_split_table_row` / `_pack_markdown_blocks_for_weixin` 全部存在且调用正确
- 无 .rej/.orig 残留

## Config 迁移（33 → 37）

- `hermes config migrate` 成功
- **personality 被重置为 none（原为 kawaii）** — 迁移器自动行为，需要时手动 `/personality kawaii` 恢复
- delegation.max_iterations 50→250、max_concurrent_children 3→10（迁移器自动提升，可用 config 恢复旧值）
- 主模型 gpt-5.6-sol / shayulajiao (api_mode: codex_responses) 配置完好

## 其他

- SOUL.md 与备份一致，无需恢复
- 依赖无新增（requirements.txt 已移除，迁移到 pyproject.toml），核心模块导入 OK
- doctor：仅 web/ui-tui npm 漏洞提示，非阻断
- 临时 swap 已清理，保留 /swapfile（2G）+ /swapfile-hermes-update（2G）
- TERMINAL_CWD 在 .env 中已废弃（非本次引入，未处理）

## 遗留

- 需主人手动 `hermes gateway restart` 生效（本次未重启）
- personality kawaii 是否恢复待主人决定
