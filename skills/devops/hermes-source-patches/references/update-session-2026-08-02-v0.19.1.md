# 更新会话 2026-08-02 — v0.19.0 → v0.19.1 (1406 commits)

## 概要

- 跨度：`5771a6ebe` → `87bc71060`（1406 commits，3468 文件变更）
- 版本：v0.19.1 (2026.7.30)
- 方式：**hermes-safe-update 控制仓库安全更新流程**（首次真实演练）
- 结果：**成功**。三个本地补丁全部干净应用，Web UI 重建完成，Gateway/Dashboard 重启正常，健康检查 failures=0，控制仓库已打 known-good 标签 `known-good-20260802-032257`。

## 过程中发现并修复的两个根因

### 1. 更新器被 Gateway 连带杀掉（首次 apply 失败的主因）

现象：`hermes-safe-update --apply` 从 Gateway 进程树内运行时，`systemctl stop hermes-gateway.service` 导致整个 Gateway cgroup 被 systemd 终止，更新器进程随之一同被杀。日志停在 "Stopping Gateway"，官方更新器根本没执行，自动回滚分支也没有机会触发。

根因：Gateway 的 systemd unit `KillMode=mixed` + cgroup 继承。从 Gateway 进程启动的子进程（包括我们手动跑的 safe-update）都在 `hermes-gateway.service` 的 cgroup 内，停止服务时全部被清。

修复：`hermes-safe-update --apply` 现在通过 `systemd-run --unit=<name> --collect` 把正式更新移交给**独立 transient systemd unit** 托管，脱离 Gateway cgroup。更新器停止 Gateway 后自己存活，失败时 ERR trap 才能真正执行独立回滚。

```bash
# 独立单元名格式
hermes-safe-update-YYYYMMDD-HHMMSS-<pid>.service
# 查看进度
journalctl -u hermes-safe-update-*.service -f
```

关键参数：`--working-directory`、`--setenv=PATH/HOME/HERMES_HOME/HTTP(S)_PROXY/NO_PROXY` 必须显式传递，transient unit 不继承调用方环境。

### 2. package-lock.json 污染候选预检

现象：预检时 `git apply --3way` 报 `package-lock.json with conflicts`，worktree 出现 `U package-lock.json`。

根因（两处）：
1. safe-update 用 `git -C "$HERMES_DIR" diff --binary > "$PATCH"` 把所有 dirty 文件（含 lockfile）全部打进候选补丁。npm 生成物不应作为源码补丁注入。
2. pathspec 排除写法 `git -C dir diff -- . ':(exclude)...'` 在 Gateway cwd（`/root/.hermes`）下失效——`.` 相对 cwd 解析，而 Gateway 的 WorkingDirectory 不是仓库根。必须 `( cd "$HERMES_DIR" && git diff ... )` 子 shell 锚定。
3. 另有一处旧的全量 diff 命令残留（health-check 之后），覆盖了过滤后的 PATCH。

修复：改用 git pathspec 排除（`:(exclude)package-lock.json` 等），并在子 shell 中 cd 到仓库根执行。lockfile 由官方更新器的依赖步骤重新生成，快照仍完整保存用于回滚。

## 当前维护结论（2026-08-02 更新后）

三个补丁保持有效，均已按新版本源码重新生成：

| 文件 | Patch | 状态 |
|------|-------|------|
| `gateway/platforms/weixin.py` | weixin-markdown-passthrough.patch | 保留，干净应用 |
| `plugins/platforms/dingtalk/adapter.py` | dingtalk-proactive-send.patch | 保留，干净应用 |
| `tools/delegate_tool.py` | delegate-tool.patch | 保留，干净应用 |

上游 1406 commits 未吸收这三个改动（补丁语义抽查通过：marker 行在候选版本中由补丁重新引入）。

## 控制仓库（hermes-safe-update）状态

- 位置：`/root/.hermes-control/`
- 更新/回滚/健康检查/快照脚本全部可用
- `hermes-safe-update --prepare`：预检（隔离 worktree + 语法 + 导入 + 补丁兼容性）
- `hermes-safe-update --apply --restart-approved`：完整流程（独立 unit + 快照 + 官方更新 + 补丁校验 + 重启 + 健康检查 + known-good 标签）
- 更新前必须先 `--prepare` 确认全绿；apply 需要主人明确授权（`--restart-approved`）

## 遗留观察项

- 中转站 shayulajiao.xyz 更新后间歇性 502（Cloudflare origin bad gateway），主模型 gpt-5.6-sol 调用重试，健康检查模型探测 WARN（非 FAIL）。Hermes 自动 fallback 到 deepseek-v4-flash，当前会话正常。中转站恢复后自动回切。
- 微信 iLink 发送在频繁消息时出现 rate limit（30s cooldown），属正常限流，非故障。
- Telegram 在重启后需重新发现 fallback IP（DNS-over-HTTPS），连接中。
