# 自定义源码修改记录

> 更新 Hermes 后运行: `bash ~/.hermes/skills/devops/hermes-source-patches/scripts/restore-all.sh`
> 详细说明见各 patch 文件头部注释。

## 修改清单

### 1. dingtalk-proactive-send.patch
- **文件**: `plugins/platforms/dingtalk/adapter.py`（v0.17.0 起从 `tools/send_message_tool.py` 迁移到插件）
- **改了什么**: `_standalone_send()` 优先通过 Robot OpenAPI 发送主动消息
- **为什么**: 默认 webhook 只能被动回复，无法主动发消息给群
- **流程**: client_id/client_secret → OAuth token → POST /v1.0/robot/groupMessages/send，失败回退 webhook
- **更新历史**: v0.17.0 (1320 commits) 上游将 dingtalk 适配器从 `tools/send_message_tool.py` 迁移到 `plugins/platforms/dingtalk/adapter.py`，旧 patch 目标文件失效，手动在新位置重新应用

### 2. weixin-markdown-passthrough.patch
- **文件**: `gateway/platforms/weixin.py`
- **改了什么**: `format_message()` 中的 `_normalize_markdown_blocks(content)` 替换为 `_convert_markdown_for_weixin(content)`，保留外层包装。同时新增 `_rewrite_table_block_for_weixin()` 辅助函数（patch 中 `_convert_markdown_for_weixin` 内部的 `_flush_table()` 调用它，将 Markdown 表格转为 `header: value | header: value` 可读格式）
- **为什么**: 微信已原生支持 Markdown 渲染，不需要再做 normalize 转换
- **注意**: 上游的格式管线一直在演变（v0.12: `_convert_markdown_for_weixin`，v0.13: `_normalize_markdown_blocks`，v0.14: `_wrap_copy_friendly_lines_for_weixin(_normalize_markdown_blocks(...))`），每次更新需检查 `format_message()` 的当前状态并适配外层包装
- **更新历史**: v0.13.0 (826 commits) Hunk #2 失败 — 上游新增 `_wrap_copy_friendly_lines_for_weixin()` 包装层，手动适配。v0.14.0 (409 commits) 同一 hunk 再次因包装层偏移失败，同样手动保留外层包装、替换内层函数

### 3. delegate-tool.patch
- **文件**: `tools/delegate_tool.py`
- **改了什么**: 在 `_build_child_agent()` 中添加一行 debug 日志，打印子代理的 model 参数和实际生效模型
- **为什么**: 调试子代理模型选择问题 — `delegate_task` 返回的 metadata 里 model 字段可能不准确，需要日志确认实际用了哪个模型

### 4. xiaomi_tts_tool.py.bak (新文件)
- **文件**: `tools/xiaomi_tts_tool.py`
- **改了什么**: 自定义小米 TTS 工具，通过 MiMo chat/completions + audio 参数生成语音
- **为什么**: Hermes 内置 TTS 不支持 xiaomi provider，MiMo TTS 用的是不同 API 格式
- **用法**: 注册为 `xiaomi_tts` 工具，语音: 茉莉/冰糖/苏打/白桦/Mia/Chloe/Milo/Dean

### 5. compression-context-provider-bug.md (config workaround, 非源码 patch)
- **文件**: `~/.hermes/config.yaml` (auxiliary.compression.context_length)
- **改了什么**: 显式指定压缩模型 context_length: 1000000，绕过自动检测
- **为什么**: run_agent.py 传错 provider，OpenRouter 免费档返回 131K 阉割值
- **详情**: `references/compression-context-provider-bug.md`
- **注意**: 换压缩模型时需同步修改或删除此配置

### 6. weixin-dedup-race-fix.patch
- **文件**: `gateway/platforms/weixin.py`
- **改了什么**: (a) `_process_message()` 中用去掉 `[引用:…]`/`[引用媒体:…]` 前缀的纯用户文本计算 content_key（稳定 dedup key）；(b) 新增第三层去重（time-window content dedup），`_recent_content` dict 在同一同步步骤中完成检查+注册，5 秒窗口内同 sender 同 text 直接丢弃；(c) dedup 日志从 DEBUG 提升到 INFO
- **为什么**: iLink getupdates API 把同一条消息返回两次（不同 message_id），且两次返回的 `ref_msg` 元数据可能不同 → `_extract_text()` 提取的文本不同 → 原有 content_key 不同 → 去重失败 → 重复回复
- **根因细节**: 原有 content_key 基于 `_extract_text()` 的完整输出（含引用文本前缀），但 iLink 两次返回同一消息时 ref_msg 内容可能不一致。修复后 content_key 只用 `\n` 之后的纯用户文本计算 hash，确保两次返回产生相同的 dedup key
- **时间窗口原理**: `_recent_content[sender:text_hash]` → check+write 是原子操作（无 await 点），消除 MessageDeduplicator check-then-register 的竞态窗口
- **更新历史**: v0.17.0 首次添加（2026-06-21），后于 2026-06-21 补充 ref_msg 前缀剥离逻辑
- **上游相关 PR**: #16646（content dedup with time buckets, 60s window, SHA-256）、#32406（write-before-process race fix）。两者均为 open 状态（截至 2026-06-21），均未覆盖 ref_msg 导致 content_key 不一致的问题。如需提 PR 向上游贡献，建议在 #16182 下补充 ref_msg 角度

### 7. reasoning-effort-custom-provider-run-agent.patch
- **文件**: `run_agent.py`
- **改了什么**: `_supports_reasoning_extra_body()` 方法新增自定义 provider 支持检查 — 当 `reasoning_config` 配置了有效的 effort（low/medium/high）且 reasoning 未被禁用时，返回 True
- **为什么**: shayulajiao 等自定义 provider 的子代理请求中 `reasoning_effort` 没有被传给 API，因为 `_supports_reasoning_extra_body()` 只对 OpenRouter、LM Studio、Nous 等已知平台返回 True
- **注意**: 插入位置在 LM Studio 检查之后、openrouter 检查之前，确保不干扰已有平台的 reasoning 逻辑

### 8. reasoning-effort-custom-provider-chat-completions.patch
- **文件**: `agent/transports/chat_completions.py`
- **改了什么**: legacy 路径（非 profile 路径）新增通用 `reasoning_effort` 兜底逻辑：当 provider 不是 Kimi/TokenHub/LM Studio、但 `supports_reasoning=True` 且 `reasoning_config` 有合法 effort 值时，在 api_kwargs 顶层添加 `reasoning_effort` 参数
- **为什么**: 自定义 provider 缺少 Kimi/TokenHub 等专属分支，导致即使 `_supports_reasoning_extra_body()` 返回 True，顶层 `reasoning_effort` 也不会被设置
- **注意**: 插入位置在 LM Studio 处理后、extra_body 组装前，仅作用于 legacy（非 profile）路径

## 调试工作流

1. **先诊断，后打补丁** — 用户明确要求"先不改，查明具体原因"。先加 WARNING 级诊断日志（记录原始字段如 message_id、content_key 等），重启观察，确认根因后再写 patch。
2. **改完要自查** — 用户会要求"再检查一下"。patch 后重新读修改区域，验证语法、逻辑、边界条件。
3. **注意当前 bug 对操作的影响** — 如重复回复 bug 可能导致 agent 自己的操作被执行两次，需要在回复中提醒用户。
4. **先对比上游源码，再归因** — 发现 bug 时，先 `git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /tmp/hermes-upstream` 拉上游代码，`diff` 对比被修改文件，确认本地 patch 没有引入问题后再归因是上游 bug。不要凭推测下结论。
5. **提 PR 前先搜现有 issue/PR** — 用 GitHub API 搜索：`curl -s "https://api.github.com/search/issues?q=repo:NousResearch/hermes-agent+<关键词>"`。已有 PR 时在相关 issue 下评论补充新发现的角度（如 ref_msg 导致 content_key 不一致），而非重复提 PR。

## 注意事项

- `__pycache__` 需要清理，否则旧 .pyc 可能覆盖新代码
- patch 可能和新版冲突，恢复时注意看输出
- 如果 patch 失败，手动检查: `cd /usr/local/lib/hermes-agent && git diff`
- 手动修复冲突后必须重新生成 .patch 文件，否则下次恢复会再次失败
