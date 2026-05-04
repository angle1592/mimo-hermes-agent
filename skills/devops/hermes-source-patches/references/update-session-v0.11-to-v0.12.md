# 更新记录：v0.11.0 → v0.12.0

**日期**: 2026-05-01
**Commits**: 319
**结果**: 4 个 patch 全部无冲突自动适配

## 更新前兼容性分析

| Patch | 上游改动 | 结果 |
|-------|---------|------|
| weixin-markdown-conversion | 上游改了 session 过期检测（+`_is_stale_session_ret`）、加了 `.flac` 音频支持。**不涉及 format_message / _convert_markdown_for_weixin 区域** | ✅ 无冲突，偏移 12/25 行 |
| dingtalk-proactive-send | 上游加了平台插件化（`Platform()` 动态解析）、`_send_via_adapter()`、Yuanbao 原生发送。**_send_dingtalk 函数未改** | ✅ 无冲突，偏移 160 行 |
| delegate-tool | 上游零改动 | ✅ 直接应用 |
| xiaomi_tts_tool.py | 独立新文件，不影响 | ✅ 直接复制 |

## 更新过程遇到的问题

1. **`patch` 命令未安装** — 阿里云 Linux 默认没有。restore-all.sh 静默跳过了所有 patch。解决：`yum install -y patch`，之后在 restore 脚本中加了依赖检查。

2. **`--forward` 静默跳过** — 当 patch 已经应用或上下文不匹配时，`patch -p1 --forward` 不报错直接跳过。需要通过 `git diff --stat` 确认改动行数是否与预期一致。

3. **git stash 不可靠** — 旧改动存在 stash 里，但更新后 stash 的上下文已经变了。正确的做法是：stash 只用于紧急回滚，patch 文件才是权威来源。更新后应立即 `git stash drop`。

## v0.12.0 重要新功能

- 平台插件化（12 个集成点，动态加载）
- Microsoft Teams 适配器（插件形式）
- Piper 本地 TTS 引擎
- TTS command-type provider（`tts.providers.<name>`）
- 多图原生发送（Telegram/Discord/Slack/Mattermost/Signal/Email）
- `/reload-skills` 命令
- Dashboard 模型配置页
- Kanban 工具
- MiniMax OAuth 完整集成
- Curator 改进（最常用/最少用 skill 统计）

## 迁移机会

新版 TTS 支持 `tts.providers.<name>` command-type provider，可以在 config.yaml 中配置 shell 命令作为 TTS 后端。`xiaomi_tts_tool.py` 未来可迁移到这个架构，不再需要维护源码 patch。
