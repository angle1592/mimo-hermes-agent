# Hermes v0.19.0 更新记录（2026-07-21）

## 范围

- 更新前提交：`7f12d4f8907f3f022653ad1250992e1d5362caed`
- 更新后稳定落点：`7a8852ddcb008523a6ea8e8acf3f22b903871495`
- 正式版本：v0.19.0（Quicksilver）
- 备份：`/root/hermes-preupdate-20260721-142426`

## 补丁结论

- DingTalk proactive send：保留，可自动应用，Robot OpenAPI 重启前后均实测成功。
- Weixin Markdown conversion：保留，可自动应用，标题、表格、代码块输出实测通过。
- Weixin dedup：重写。复用上游原子的 `MessageDeduplicator.is_duplicate()`；只保留引用前缀归一化和 INFO 日志，删除重复的 `_recent_content` 缓存。
- Delegate debug：保留，可自动应用；v0.19.0 原生新增 live transcripts。
- Custom provider reasoning patches：继续退休；`shayulajiao` 的 `gpt-5.6-sol` 主模型 high、子代理 xhigh 由 CustomProfile 原生支持。

## 恢复脚本改进

- 支持 `HERMES_DIR=/tmp/worktree`，可以真正隔离预检。
- 补丁失败时返回非零，不再把“已存在或冲突”静默当成功。
- 禁止生成 `.orig`，reject 输出到标准输出；任何失败均需人工检查。

## 验证

- 隔离定向测试：503 passed，1 skipped。
- 生产完整定向测试：502 passed，1 skipped。
- 尾部 6 个核心修复后的最小回归：115 passed。
- `hermes config check`：配置 v33。
- `hermes doctor`：版本一致 v0.19.0；无活跃安全公告。仅两个前端 build-time npm advisory。
- 主模型真实调用：更新前后分别返回 `MODEL_OK`、`POST_RESTART_MODEL_OK`。
- DingTalk Robot OpenAPI：更新前后均返回 `success: true`。
- Gateway：新 PID `1029217`，systemd active。
- Dashboard/Token Monitor：健康接口 HTTP 200。
- Weixin：重启后当前微信消息成功进入新 Gateway；出站曾遇到 iLink 30 秒 rate limit，属于平台限流，不是启动失败。
- Telegram：代理 HTTP 探针返回 302；运行中曾有可恢复的网络断连重试。

## 已知非阻断问题

- 一次性 `hermes chat -q` 在旧一轮探针退出时曾打印 MCP subprocess `Event loop is closed` 清理告警，API 调用本身成功；重启后复测未再出现。
- 从 Gateway cgroup 内启动普通后台 shell 后直接 `systemctl restart hermes-gateway`，shell 会随 cgroup 一起被杀。更新时重启验收应使用 `systemd-run --on-active` 的 PID 1 transient unit，不能只用 terminal background。
- 上游 main 持续滚动。本次以通过验证的 `7a8852ddc` 为稳定落点；之后新增的 Billing/Relay/TUI 提交不触及本机功能或补丁文件，未继续追赶。
