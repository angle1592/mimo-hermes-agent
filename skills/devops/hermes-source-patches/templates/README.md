# 自定义源码修改记录

> 更新 Hermes 后运行: `bash ~/.hermes/patches/restore-all.sh`
> 详细说明见各 patch 文件头部注释。

## 修改清单

### 1. dingtalk-proactive-send.patch
- **文件**: `tools/send_message_tool.py`
- **改了什么**: `_send_dingtalk()` 优先通过 Robot OpenAPI 发送主动消息
- **为什么**: 默认 webhook 只能被动回复，无法主动发消息给群
- **流程**: client_id/client_secret → OAuth token → POST /v1.0/robot/groupMessages/send，失败回退 webhook

### 2. weixin-markdown-conversion.patch
- **文件**: `gateway/platforms/weixin.py`
- **改了什么**: 新增 `_convert_markdown_for_weixin()` 函数，`format_message()` 从 `_normalize_markdown_blocks` 改为调用它
- **为什么**: 微信 iLink Bot API 不支持 Markdown 渲染，发出去会显示原始语法符号
- **转换规则**: #→【】、**→去除、`→「」、- →·、>→│、表格→列表、链接→text (url)

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

## 注意事项

- `__pycache__` 需要清理，否则旧 .pyc 可能覆盖新代码
- patch 可能和新版冲突，恢复时注意看输出
- 如果 patch 失败，手动检查: `cd /usr/local/lib/hermes-agent && git diff`
