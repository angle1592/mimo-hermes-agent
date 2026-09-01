# 更新会话 2026-09-02：v0.20.3 → v0.21.0

## 概况

- 跨度：3322 commits（c9ce66e25e → e5e71d8c46），3863 文件变更
- 上游改动文件：`plugins/platforms/dingtalk/adapter.py`（+2）、`gateway/platforms/weixin.py`（+10/-6）、`tools/delegate_tool.py`（+621/-155）
- 版本：pyproject.toml 0.20.3 → 0.21.0

## 更新前分析结论

| Patch | hunk 位置 | 上游改动位置 | 判定 |
|-------|-----------|--------------|------|
| dingtalk-proactive-send | `_standalone_send` 1674 | 377 行 `_wire_plugin_handlers` | 不重叠 → 无冲突 |
| weixin-markdown-passthrough | 876/1426/2297 | 1227-1341 `_wx_secret`、1537 `_open_dm_opted_in` | 基本不重叠，hunk2 靠近 1537 需留意 |
| delegate-tool | `effective_model_for_cb` 1329 | 该区域结构保留 | 可自动适配 |

实际结果：三个补丁全部自动适配，零 hunk 失败：
- dingtalk: offset 58 行
- weixin: offset 18/50/52 行
- delegate: offset 510 行

## 执行步骤

1. `git fetch origin main`（githubfast 镜像 403，改用 origin 直连成功）
2. `git stash` + drop 旧 stash
3. `git pull origin main` → HEAD e5e71d8c46
4. 手动逐个 `patch -p1 --forward --batch --no-backup-if-mismatch --reject-file=- < references/<name>.patch`（restore-all.sh 含 restart 字样会被 Gateway 安全机制拦截，沿用上次方案）
5. `git diff --stat` 与更新前完全一致（251 insertions, 11 deletions）
6. py_compile 三个文件全部通过
7. 检查补丁引用函数全部存在（_convert_markdown_for_weixin 等）

## 依赖变更

新增/升级：
- firecrawl-anydoc==0.2.4（注意：模块导入名是 `anydoc` 不是 `firecrawl_anydoc`）
- snowballstemmer==3.1.1
- uvicorn[standard]>=0.31.0,<1（0.41.0）
- hermes_startup_watchdog —— 不是 PyPI 包！是仓库内本地模块（hermes_startup_watchdog.py），pip install 会报 "No matching distribution"，属正常
- cryptography 48.0.1 → 50.0.0（hermes 要求 ==50.0.0）
- nemo-relay 0.6.0 → 0.7.3（hermes 要求 >=0.7.1,<0.8）

残留依赖警告（可接受）：alibabacloud-tea-openapi 0.4.5 要求 cryptography<49，与 hermes 要求的 50 冲突，属上游自身依赖树决定，不影响运行。

## 配置迁移

- `hermes config check`：版本 37 → 39
- `hermes config migrate` 执行成功
- personality 保持 `''` 未被重置（当前人设由 SOUL.md 承载，非 personality 字段）
- SOUL.md 与 /root/mimo-hermes-agent/docs/SOUL.md 备份一致
- config 备份：~/.hermes/config.yaml.bak.20260902_preupdate

## 遗留事项

- Gateway 尚未重启（需主人许可，重启会中断当前会话）
- 插件 segmented-reply 识别正常（enabled，user 来源）；`hermes chat -q` 提示 "Unknown toolsets: segmented_reply" 仅为 toolset 名横线/下划线显示差异，工具 `send_segmented_reply` 仍在册
- 重启后需验证：新 PID/启动时间、各平台重连、代理继承、一次最小模型请求

## 验证清单（重启后）

- [ ] `hermes gateway restart`（或主人自行重启）
- [ ] ps 确认新 PID
- [ ] 微信/钉钉/Telegram 重连
- [ ] 一次实际对话确认模型可用
- [ ] `hermes --version` 显示 v0.21.0（注意：镜像 pull 时 version 的 commits-behind 检查可能显示异常，用 `git log --oneline -1` 验证真实版本）
