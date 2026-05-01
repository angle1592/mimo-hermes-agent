---
name: hermes-source-patches
description: "Hermes 源码自定义修改记录 — 更新前必须读，恢复用 restore-all.sh"
version: 1.0.0
tags: [hermes, patches, source-modification]
---

# Hermes 源码自定义修改

## 触发条件
- 更新 Hermes Agent 前后
- 需要修改 Hermes 源码时
- Gateway 出现功能异常时（可能是 patch 被覆盖）

## 完整修改记录

修改详情见 `templates/README.md`（本 skill 目录内）。

更新历史见 `references/update-session-v0.11-to-v0.12.md`（真实案例：319 commits，4 个 patch 全部无冲突自动适配）。

当前已保存的 patch（本 skill `references/` 目录内）：

| 文件 | Patch | 用途 |
|------|-------|------|
| `tools/send_message_tool.py` | references/dingtalk-proactive-send.patch | 钉钉群主动发消息（Robot OpenAPI） |
| `gateway/platforms/weixin.py` | references/weixin-markdown-conversion.patch | 微信 Markdown→纯文本转换 |
| `tools/delegate_tool.py` | references/delegate-tool.patch | 子代理模型 debug 日志 |
| `tools/xiaomi_tts_tool.py` | references/xiaomi_tts_tool.py.bak | 小米 TTS 自定义工具（新文件） |

## 更新前分析流程

更新 Hermes 前，逐个检查每个 patch 的上游兼容性：

```bash
cd /usr/local/lib/hermes-agent

# 1. 确认当前版本和差距
hermes --version
git log --oneline HEAD..origin/main | wc -l

# 2. 查看上游对每个被修改文件的改动
git diff HEAD..origin/main -- <file>

# 3. 对比 patch 的改动区域和上游改动是否重叠
grep -n "^@@" ~/.hermes/skills/devops/hermes-source-patches/references/<name>.patch
```

判断标准：
- **无冲突**：上游改动和 patch 改动区域不重叠 → `patch -p1` 可自动应用
- **有冲突**：同一区域被双方修改 → 需要手动合并或重写 patch
- **函数签名变了**：patch 能 apply 但逻辑可能不对 → 需要 review

## 完整更新流程

```bash
cd /usr/local/lib/hermes-agent

# 0. 确认 patch 命令已安装（阿里云 Linux 默认没有！）
command -v patch || yum install -y patch

# 1. 分析上游改动（逐文件检查是否与 patch 区域重叠）
git diff HEAD..origin/main -- <file> | head -200
grep -n "^@@" ~/.hermes/skills/devops/hermes-source-patches/references/<name>.patch

# 2. 丢弃旧 stash（patches 目录才是权威来源）
git stash 2>/dev/null; git stash drop 2>/dev/null

# 3. 拉取新版
git pull origin main

# 4. 恢复 patches
bash ~/.hermes/skills/devops/hermes-source-patches/scripts/restore-all.sh

# 5. 验证（关键！确认改动行数与更新前一致）
git diff --stat              # 应与更新前的输出一致
python3 -c "import py_compile; py_compile.compile('<modified_file>', doraise=True)"
hermes --version

# 6. 重启 Gateway（注意：会中断当前会话！让用户自行重启）
echo "请执行: hermes gateway restart"
```

### 更新前必须告诉用户的事项

- 更新会中断当前会话（Gateway 重启）
- 更新前应先分析兼容性，确认 patch 无冲突再执行
- **不要自行重启 Gateway**，让用户在方便时重启

## 一键恢复

```bash
cd /usr/local/lib/hermes-agent && bash ~/.hermes/skills/devops/hermes-source-patches/scripts/restore-all.sh
```

恢复后需要重启 Gateway 才能生效。如果 patch 失败，检查输出手动修复。

## Pitfalls

1. **`patch` 命令未安装** — restore-all.sh 会静默跳过所有 patch！阿里云 Linux 默认没有 `patch`。安装：`yum install -y patch`。restore 脚本应加依赖检查：`command -v patch >/dev/null 2>&1 || { echo "需要安装 patch"; exit 1; }`

2. **`--forward` 静默跳过** — `patch -p1 --forward` 在上下文不匹配时直接跳过不报错。恢复后务必用 `git diff --stat` 确认改动行数与更新前一致。

3. **行号偏移** — 上游新增代码会导致 patch 的行号偏移，但 `patch` 会自动用上下文匹配（`offset N lines`）。只要上下文没变就能自动适配。

4. **stash 不是 source of truth** — `git stash` 里的旧改动可能与新版冲突。patches 目录才是权威来源。stash 确认 patches 恢复成功后应立即 drop。

5. **新版本可能改变适配器架构** — 如 v0.12.0 的平台插件化。需要额外检查 patch 目标文件是否被重构（函数签名、导入路径等）。

## 新增修改的规范

每次修改 Hermes 源码时，必须同步执行：

1. 保存 patch: `cd /usr/local/lib/hermes-agent && git diff <file> > ~/.hermes/skills/devops/hermes-source-patches/references/<name>.patch`
2. 新文件备份: `cp <file> ~/.hermes/skills/devops/hermes-source-patches/references/<name>.bak`
3. 更新 `templates/README.md` 记录改了什么、为什么改
4. 如果 `scripts/restore-all.sh` 需要新的恢复步骤，同步更新

## 知识分层架构

修改记录分布在三层，各司其职：

| 层级 | 位置 | 内容 | 何时读 |
|------|------|------|--------|
| 记忆 | memory entry | 一行指针："源码 patch 存在，详情加载 skill" | 每轮自动注入 |
| Skill | hermes-source-patches | 流程、规范、pitfalls | 修改源码/更新时加载 |
| README | skill: templates/README.md | 每个 patch 的详细说明 | skill 内读取 |

**不要每次都读 README**——随着 README 增大会浪费上下文。记忆只放指针，skill 放流程，README 放详情。

## 迁移机会

新版 v0.12.0 的 TTS 支持 `tts.providers.<name>` command-type provider（config.yaml 中配置 shell 命令）。`xiaomi_tts_tool.py` 未来可以迁移到这个架构，就不需要维护源码 patch 了。

迁移方案：在 `~/.hermes/config.yaml` 中配置：
```yaml
tts:
  providers:
    xiaomi:
      type: command
      command: "python3 /path/to/xiaomi_tts.py --text {text} --output {output}"
      format: wav
```
这样 TTS 逻辑变成独立脚本，不侵入 Hermes 源码，更新也不会被覆盖。

## 关键路径

- Skill 根目录: `~/.hermes/skills/devops/hermes-source-patches/`
- Patch 文件: `references/` 子目录
- 恢复脚本: `scripts/restore-all.sh`
- 修改说明: `templates/README.md`
- 源码目录: `/usr/local/lib/hermes-agent/`

## 用户偏好

- 源码修改必须留下可读说明（README.md / patch 头部注释），不能只靠记忆传递。类似 CLAUDE.md / AGENTS.md 的理念——持久化文档比记忆更可靠。
- 更新前先分析兼容性，确认无冲突后再执行。不要盲目更新。
