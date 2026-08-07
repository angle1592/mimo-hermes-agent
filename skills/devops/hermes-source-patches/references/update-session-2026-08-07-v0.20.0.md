# Hermes v0.19.1 → v0.20.0 更新记录（2026-08-07）

## 结果

- 起点：`c7b4b4e178d3`，Hermes Agent v0.19.1。
- 终点：`55505be152e3`，Hermes Agent v0.20.0。
- 本地修改：`gateway/platforms/weixin.py`、`plugins/platforms/dingtalk/adapter.py`、`tools/delegate_tool.py` 均由官方 updater stash/restore 后保留，语法检查通过。
- known-good：`known-good-20260807-125242`。
- 事务快照：`/root/.hermes-control/snapshots/history/20260807-125238`。

## 首次失败与根因

首次更新代码和依赖均成功，但 `Type=notify` 的 Gateway 启动超过 systemd 默认 90 秒，`systemctl restart` 返回 `start operation timed out`，安全更新器按设计触发回滚。回滚后的 Gateway 也因同一 90 秒限制多次启动超时，最终由 `Restart=always` 拉起。

根因不是补丁冲突，而是 2C/2G 主机在 Web UI 构建、依赖更新、Dashboard 重启和 Gateway 初始化 MCP/三平台叠加时资源紧张。

## 修复

控制仓库 `/root/.hermes-control` 提交 `1625f67`：

1. 新增 `/etc/systemd/system/hermes-gateway.service.d/startup-timeout.conf`：`TimeoutStartSec=300s`。
2. `hermes-safe-update` 在启动 Gateway 前停止 Dashboard，Gateway 两级健康检查后恢复 Dashboard。
3. `hermes-rollback` 使用同一资源编排，异常路径也 best-effort 恢复 Dashboard。
4. 新增回归测试 `tests/test-update-startup-policy.sh`，并保留原有 `test-safe-update-interface.sh`。

## 实际验证

- 回归测试、Shell 语法、`systemd-analyze verify`、隔离 worktree 预检均通过。
- systemd 解析：`TimeoutStartUSec=5min`、`WatchdogUSec=2min`、`Type=notify`。
- 第二次事务更新完成，完整 health check 和独立最小模型探针通过。
- Gateway 首次启动阶段在高内存/高 swap 压力下被 watchdog 拉起两次，最终 PID 稳定并进入 active；因此更新后必须检查 `NRestarts` 和 watchdog 日志，不能只看 updater 退出码。
- DingTalk、Weixin、Telegram 均连接成功，日志显示 `Gateway running with 3 platform(s)`；Weixin 已完成真实入站及模型调用。
- Dashboard active；代理环境变量、SOUL、技能和 watchdog 配置保留。

## 后续注意

- v0.20 更新后首次启动可能有较长冷启动；不要把 `TimeoutStartSec` 降回 90 秒。
- `WatchdogSec=120s` 仍保留，负责运行期事件循环卡死恢复；启动超时与 watchdog 是两条独立保护线。
- `time` MCP 连接失败是独立遗留问题，不影响本次更新验收。
