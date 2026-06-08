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

更新历史见 `references/update-session-v0.11-to-v0.12.md`（319 commits，4 个 patch 全部无冲突自动适配）、`references/update-session-2026-05-05.md`（302 commits，offset 最大 +178 行，全部自动适配）、`references/update-session-2026-05-15.md`（1006 commits，2 个 patch 需手动修复）、`references/update-session-2026-05-22.md`（826 commits，weixin patch 手动适配外层包装函数）、`references/update-session-2026-05-24.md`（409 commits，weixin hunk 2 因上游加 `_wrap_copy_friendly_lines_for_weixin` 包装需手动适配）和 `references/update-session-2026-05-31.md`（12 commits，fast-forward，零冲突）。

当前已保存的 patch（本 skill `references/` 目录内）：

| 文件 | Patch | 用途 |
|------|-------|------|
| `tools/send_message_tool.py` | references/dingtalk-proactive-send.patch | 钉钉群主动发消息（Robot OpenAPI） |
| `gateway/platforms/weixin.py` | references/weixin-markdown-conversion.patch | 微信 Markdown→纯文本转换（旧，已被 passthrough 替代） |
| `gateway/platforms/weixin.py` | references/weixin-markdown-passthrough.patch | 微信 Markdown 透传（替换 normalize 为 convert，保留外层包装） |
| `tools/delegate_tool.py` | references/delegate-tool.patch | 子代理模型 debug 日志 |
| `tools/xiaomi_tts_tool.py` | references/xiaomi_tts_tool.py.bak | 小米 TTS 自定义工具（新文件） |
| `run_agent.py` | references/compression-context-provider-bug.md | 压缩模型上下文误用主模型 provider（v0.12.0 bug，config workaround） |

## 更新前分析流程

更新 Hermes 前，逐个检查每个 patch 的上游兼容性：

```bash
cd /usr/local/lib/hermes-agent

# 1. 确认当前版本和差距
hermes --version
git log --oneline HEAD..origin/main | wc -l

# 2. 查看上游对每个被修改文件的改动
git diff HEAD..origin/main -- <file>

# 2b. 或者逐 commit 检查哪些文件被碰过（大跨度更新推荐）
for commit in $(git log --format='%H' HEAD..origin/main); do
  echo "=== $(git log --oneline -1 $commit) ==="
  git diff --name-only $commit~1 $commit 2>/dev/null
done
# → 如果没有任何 commit 碰到 patched 文件，patch 必然无冲突

# 3. 对比 patch 的改动区域和上游改动是否重叠
grep -n "^@@" ~/.hermes/skills/devops/hermes-source-patches/references/<name>.patch
```

判断标准：
- **无冲突**：上游改动和 patch 改动区域不重叠 → `patch -p1` 可自动应用
- **有冲突**：同一区域被双方修改 → 需要手动合并或重写 patch
- **函数签名变了**：patch 能 apply 但逻辑可能不对 → 需要 review

## 更新前安全检查

**在执行任何更新操作之前**，确认以下两项：

```bash
# 1. Swap 必须存在（2GB 机器无 swap 更新会直接卡死！）
swapon --show
# 如果为空 → 先加 swap，再更新。详见 deploy-service-china skill Step 0。

# 2. 确认 patch 命令已安装
command -v patch || yum install -y patch
```

### Pitfall: 无 Swap 更新 = 服务器卡死

真实案例：2C2G 服务器凌晨自动 Hermes 更新（131 commits），pip/npm 同时下载解压大量依赖包，内存和磁盘 I/O 打满，系统完全无响应，只能强制重启。没有任何 OOM 日志——内核连 OOM killer 都跑不起来。

**教训：** 更新 Hermes 不是轻量操作。大版本更新可能拉取上百个 commit 并重装大量依赖。低配机器务必先确认 swap 存在。

## 完整更新流程

```bash
cd /usr/local/lib/hermes-agent

# 0. 安全检查（必须先做！）
swapon --show                                    # 确认 swap 存在
command -v patch || yum install -y patch         # 确认 patch 命令

# 1. 分析上游改动（逐文件检查是否与 patch 区域重叠）
git fetch origin main
git diff HEAD..origin/main -- <file> | head -200
grep -n "^@@" ~/.hermes/skills/devops/hermes-source-patches/references/<name>.patch

# 2. 丢弃旧 stash（patches 目录才是权威来源）
git stash 2>/dev/null; git stash drop 2>/dev/null

# 3. 拉取新版
git pull origin main

# 4. 恢复 patches
bash ~/.hermes/skills/devops/hermes-source-patches/scripts/restore-all.sh

# 5. 如果有 hunk 失败 → 手动修复（见下方 Pitfall）
# 5a. 查看失败详情: cat <file>.rej
# 5b. 用 grep 定位当前代码: grep -n "<关键函数>" <file>
# 5c. 做针对性替换（保留上游新增的包装层/参数）
# 5d. 重新生成 patch: git diff <file> > references/<name>.patch
# 5e. 清理 reject: rm -f <file>.rej

# 6. 清理 patch 遗留文件（.orig, .rej）
rm -f gateway/platforms/weixin.py.orig tools/*.orig tools/*.rej gateway/platforms/*.rej

# 7. 验证（关键！确认改动行数与更新前一致）
git diff --stat              # 应与更新前的输出一致
python3 -c "import py_compile; py_compile.compile('<modified_file>', doraise=True)"
hermes --version

# 7. 重启 Gateway（注意：会中断当前会话！让用户自行重启）
echo "请执行: hermes gateway restart"
```

### 更新前必须告诉用户的事项

- 更新会中断当前会话（Gateway 重启）
- 更新前应先分析兼容性，确认 patch 无冲突再执行
- **不要自行重启 Gateway**，让用户在方便时重启——重启会中断当前正在运行的会话/任务
- `patch` 命令需要单独安装：`yum install -y patch`

## 一键恢复

```bash
cd /usr/local/lib/hermes-agent && bash ~/.hermes/skills/devops/hermes-source-patches/scripts/restore-all.sh
```

恢复后需要重启 Gateway 才能生效。如果 patch 失败，检查输出手动修复。

## Pitfalls

1. **`hermes --version` 在 mirror pull 后仍显示 "X commits behind"** — 当使用 `git pull https://githubfast.com/... main`（中国镜像）更新时，HEAD 已经是最新的，但 `hermes --version` 的 "commits behind" 检查对比的是 `origin/main` tracking ref（指向 GitHub 原始仓库），而不是 FETCH_HEAD。所以版本信息仍显示落后。不影响实际运行（代码已更新），但会让用户困惑。修复：更新后执行 `git fetch origin` 同步 origin ref，或告知用户这是显示问题不影响功能。验证实际版本用 `git log --oneline -1`。

2. **先查根因，再打补丁** — 用户教训：发现压缩模型上下文检测错误时，我直接加了 config 覆盖，用户问"为什么不去查查到底是什么模型、哪个供应商？"正确流程：先追踪实际调用链（provider/base_url/resolution chain），搞清楚错误值从哪来，再决定修法。config 覆盖是兜底手段，不是首选。

2. **config 修改必须留注释** — 加 context_length 等显式覆盖时，必须用 YAML 注释说明原因和换模型时的操作，否则以后自己都忘了为什么加的。

3. **`patch` 命令未安装** — restore-all.sh 会静默跳过所有 patch！阿里云 Linux 默认没有 `patch`。安装：`yum install -y patch`。restore 脚本应加依赖检查：`command -v patch >/dev/null 2>&1 || { echo "需要安装 patch"; exit 1; }`

2. **`--forward` 静默跳过** — `patch -p1 --forward` 在上下文不匹配时直接跳过不报错。恢复后务必用 `git diff --stat` 确认改动行数与更新前一致。

3. **行号偏移** — 上游新增代码会导致 patch 的行号偏移，但 `patch` 会自动用上下文匹配（`offset N lines`）。只要上下文没变就能自动适配。

4. **stash 不是 source of truth** — `git stash` 里的旧改动可能与新版冲突。patches 目录才是权威来源。stash 确认 patches 恢复成功后应立即 drop。

4. **手动修复冲突后必须重新生成 patch 文件** — `restore-all.sh` 失败的 hunk 需要手动修复，修复后旧的 .patch 文件已经过时（上下文行号、函数签名都可能变了）。必须立即 `git diff <file> > references/<name>.patch` 更新 patch 文件，否则下次恢复会再次失败。v0.13.0 更新时 weixin.py 和 delegate_tool.py 都遇到了这个问题。

5. **上游在外层加了包装函数导致 patch hunk 失败** — v0.14.0 更新时 weixin.py 的 `format_message` 从 `return _normalize_markdown_blocks(content)` 变成了 `return _wrap_copy_friendly_lines_for_weixin(_normalize_markdown_blocks(content))`。Patch 期望替换整个表达式，但新代码多了外层包装。**正确做法**：保留外层包装，只替换内层函数 → `return _wrap_copy_friendly_lines_for_weixin(_convert_markdown_for_weixin(content))`。判断方法：`cat <file>.rej` 看失败的 hunk，`grep -n` 找当前代码中目标函数的实际调用方式，对比差异后做针对性替换。

5. **新版本可能改变适配器架构** — 如 v0.12.0 的平台插件化。需要额外检查 patch 目标文件是否被重构（函数签名、导入路径等）。

5. **新版本可能改变适配器架构** — 如 v0.12.0 的平台插件化。需要额外检查 patch 目标文件是否被重构（函数签名、导入路径等）。

6. **Patch 引用的函数可能从未定义** — 2026-06-09 发现 weixin patch 的 `_convert_markdown_for_weixin` 调用了 `_rewrite_table_block_for_weixin()`，但该函数从未在文件中定义（写 patch 时遗漏）。导致所有触发表格处理的微信消息发送失败（NameError，plain-text fallback 也失败）。**教训**：apply patch 后不仅要检查语法（`py_compile`），还要用 `grep -n` 确认 patch 中调用的每个外部函数确实存在于文件中。恢复脚本也应加此检查。

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

## Xiaomi TTS 调用 Pitfall

`xiaomi_tts_tool.py` 通过 `os.getenv("XIAOMI_API_KEY")` 读取密钥。该密钥存储在 `~/.hermes/.env` 中，但 **不会自动注入到 terminal/execute_code 的子进程环境**。直接在 Python 脚本中 import 调用会返回 `"XIAOMI_API_KEY not configured"`。

**正确做法：** 在 terminal 命令中先 export 环境变量：
```bash
source ~/.hermes/.env
# 然后再调用 python 脚本
```
或者在 execute_code 中手动 `os.environ["XIAOMI_API_KEY"] = ...`。

### 可用声音

| 声音 | 性别 | 特点 |
|------|------|------|
| 茉莉 | 女 | 默认，标准中文女声 |
| 冰糖 | 女 | 偏甜美 |
| 苏打 | 女 | - |
| Mia | 女 | 英文向 |
| Chloe | 女 | 英文向，中文也能读但口音偏西 |
| 白桦 | 男 | - |
| Milo | 男 | - |
| Dean | 男 | - |

### style 参数（mimo-v2.5-tts）

普通模型支持 `style` 参数作为"导演指令"，控制语气/情感。示例：
- `用温柔甜美的语气说` — 更柔和
- `用轻松自然、像朋友聊天一样的语气说` — 去掉播音腔
- `用活泼俏皮的语气说` — 更有活力

style 越具体，效果越明显。但不要写太长，一句话即可。

### voicedesign 模型（mimo-v2.5-tts-voicedesign）

用文字描述生成全新音色，不需要预设声音。**但有两个坑：**

1. **不接受 `audio.voice` 参数** — 传了会返回 400：`audio.voice is not supported for voice design model`
2. **user message 必须非空** — 音色描述放在 `user` message 的 `content` 里，待合成文本放 `assistant` message

```python
# 正确调用方式
completion = client.chat.completions.create(
    model='mimo-v2.5-tts-voicedesign',
    messages=[
        {'role': 'user', 'content': '一个20岁左右的中国女生，声音温柔甜美，语速适中'},
        {'role': 'assistant', 'content': '你好呀，很高兴认识你！'}
    ],
    audio={'format': 'mp3'}  # 不要加 voice！
)
```

**voiceclone 模型**（mimo-v2.5-tts-voiceclone）需要上传参考音频样本，未在 Hermes 工具中集成。

## SOUL.md 自定义修改

`~/.hermes/SOUL.md` 是 Hermes Agent 的系统提示文件，每次新会话都会作为 system prompt 加载。Hermes 更新可能覆盖此文件。

**当前修改**：在末尾添加了负面表情硬约束（禁止 😅🙃😏🤣🙄💀💦🙏）。

**备份位置**：`/root/mimo-hermes-agent/docs/SOUL.md`（随 repo-sync 自动同步到 GitHub）。

**更新后恢复**：
```bash
cp /root/mimo-hermes-agent/docs/SOUL.md ~/.hermes/SOUL.md
```

## 静态文件托管（本服务器）

音频/文件可通过 nginx `/audio/` 路径对外提供：
- 目录: `/usr/share/nginx/html/audio/`
- URL: `http://YOUR_SERVER_IP/audio/`
- 无需认证 (`auth_basic off`)
- TTS 试听页: `/usr/share/nginx/html/audio/tts/index.html`

FileBrowser (`/files/` 路径) 偶尔出现 404 问题。常见原因：nginx 缺少 `/files/` 的 proxy 配置。修复：

```bash
cat > /etc/nginx/default.d/filebrowser.conf << 'EOF'
location /files/ {
    proxy_pass http://127.0.0.1:8080/files/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
EOF
nginx -t && nginx -s reload
```

重要静态文件优先放 `/audio/` 目录（已在 nginx 中配置）。

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
