# Hermes 更新失败后的事务性回滚

## 症状

大跨度更新前先执行 `git restore` 清理自定义源码改动，随后 `hermes update` 在 Git fetch 阶段网络失败。失败 trap 只重新启动 Dashboard，导致服务虽然在线，但 Weixin 去重、DingTalk 主动发送和 custom-provider reasoning 等补丁均未加载。

## 根因

更新脚本把“服务恢复”误当作“系统恢复”，没有把源码补丁状态纳入失败回滚条件。systemd unit 即使成功拉起，也可能运行降级后的上游原版代码。

## 正确恢复顺序

1. `git status --short` 和 `git diff --stat` 检查补丁是否还在。
2. 若已被清理，运行 `bash ~/.hermes/skills/devops/hermes-source-patches/scripts/restore-all.sh`。
3. 清理所有 `.orig` / `.rej`。
4. 对补丁目标 Python 文件运行 `python3 -m py_compile`。
5. 对比更新前保存的 diff stat，确认文件数和变更规模符合预期。
6. 最后启动或重启 Dashboard/Gateway。
7. 验证平台连接及关键补丁功能。

## 脚本设计要求

- 在清理补丁前保存完整 `git diff`。
- trap 中调用单独的 `restore_patches_if_needed`，再调用 `restart_dashboard`。
- trap 不能吞掉原始失败码；日志应同时记录更新失败和回滚结果。
- 临时 systemd unit 的 `Result=success` 不能作为更新成功依据；以版本、补丁状态和验证结果为准。
