# Hermes Agent 国内环境部署经验

用 [Hermes Agent](https://hermes.nousresearch.com) 搭了一个个人 AI 助手，接入微信和钉钉。模型换过几次（DeepSeek → MiMo），配置和踩坑经验记在这里，供参考。

**不保证适合所有人。** 这是个人项目的记录，不是教程。很多选择是基于我自己的需求和 2C2G 小机器的限制，不一定是最优解。

## 这是什么

一句话：一个跑在国内云服务器上的 Hermes Agent 实例，通过微信和钉钉与我交互，能记住上下文、调用工具、委派子任务。

框架本身是 [Hermes Agent](https://hermes.nousresearch.com)，它负责消息路由、记忆管理、工具调用、多 Agent 协调这些核心能力。我做的事情主要是：

- 选择和配置适合国内使用的模型提供商
- 对接微信和钉钉的 gateway
- 一些日常使用的 skill 和自动化脚本
- 在低配机器上跑起来的经验

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/angle1592/mimo-hermes-agent.git
cd mimo-hermes-agent

# 一键部署（安装 Hermes、Token 监控、Nginx）
sudo bash scripts/setup.sh

# 手动配置模型
hermes config set model.default deepseek-v4-pro
echo 'DEEPSEEK_API_KEY=sk-xxx' >> ~/.hermes/.env

# 启动
hermes gateway start
```

详细步骤见 [部署指南](docs/deployment-guide.md)，踩坑见 [踩坑记录](docs/pitfalls.md)。

## 当前配置

| 组件 | 选型 | 备注 |
|------|------|------|
| 框架 | Hermes Agent | 开源 Agent 框架 |
| 主模型 | MiMo V2.5-Pro | 通过 OpenAI 兼容接口接入 |
| 辅助模型 | DeepSeek V4 Pro / Flash | 子代理和辅助任务 |
| 消息平台 | 微信 + 钉钉 | 微信用 itchat-uos，钉钉用 Stream Mode |
| MCP 工具 | Playwright、SQLite、Sequential Thinking | 浏览器自动化、数据存储、分步推理 |
| 部署 | Alibaba Cloud Linux | 2 vCPU / 2GB RAM + 2GB swap |

模型不是固定的。之前用 DeepSeek 做主力，现在换成了 MiMo，以后可能还会变。Hermes 支持任何 OpenAI 兼容的 API，换模型只需改配置。

## 模型选择经验

不同模型各有特点，以下是实际使用感受（截至 2026 年 8 月）：

| 模型 | 特点 | 定价参考 |
|------|------|----------|
| MiMo V2.5-Pro | 推理和代码能力不错，中文理解好 | [官方定价](https://platform.xiaomimimo.com/static/docs/pricing.md) |
| DeepSeek V4 Pro | 综合能力强，工具调用稳定 | [官方定价](https://api-docs.deepseek.com/quick_start/pricing) |
| DeepSeek V4 Flash | 速度快，适合子代理和辅助任务 | 同上 |

定价会变，以官方页面为准，这里不列具体数字。

实际使用中，主模型和辅助模型搭配效果比单一模型好。比如用 MiMo 做主力推理，子代理用 DeepSeek 处理并行任务。

## 实际跑起来的一些数据

仅供参考，不同使用强度差异很大：

- 日均 Token 消耗：1,000~3,000 万（高强度日会更多）
- 缓存命中率：97% 以上（Hermes 的 context caching 机制）
- 在 2C2G 机器上能跑，但复杂任务会比较慢

## 常用场景

我日常用得比较多的几个：

- **定时推送** — 每天早上自动汇总日程和待办，推到钉钉群
- **代码相关** — 发 PR 链接让它做 review，或者让它帮忙排查问题
- **信息收集** — 描述一个话题，它会拆成几个子任务并行搜索，汇总成报告
- **文件处理** — 发 PDF 过去，提取文字后分析总结
- **服务器运维** — 直接在对话里执行 shell 命令，查日志、改配置

这些都是 Hermes 本身的能力，不是我额外开发的。我只是做了配置和一些自定义 skill。

## 项目结构

```
├── README.md
├── config/
│   ├── config.example.yaml        # 配置说明
│   └── config.yaml.example        # 脱敏后的真实配置参考
├── deploy/
│   ├── nginx/
│   │   └── hermes.conf            # Nginx 反代配置
│   └── systemd/
│       ├── hermes-dashboard.service
│       └── hermes-token-monitor.service
├── docs/
│   ├── deployment-guide.md        # 部署步骤
│   ├── mimo-integration.md        # MiMo 接入笔记
│   ├── pitfalls.md                # 踩坑记录
│   └── shared/                    # 跨 skill 共享文档
│       ├── china-infra-patterns.md  # 国内基础设施通用模式
│       └── model-pricing.md         # 模型定价参考
├── scripts/
│   ├── lib.sh                     # 共享 shell 工具（日志、颜色、脱敏）
│   ├── setup.sh                   # 一键部署脚本
│   ├── sync.sh                    # 自动同步到 GitHub
│   └── token_monitor.py           # Token 用量监控（Web 面板）
└── .gitignore
```

## 已知限制

- 2C2G 机器跑多 Agent 并行时会卡，建议 4G 以上内存
- 微信用的是 itchat-uos 协议，有封号风险，建议用小号
- 国内网络环境需要处理 GitHub 和部分 API 的访问问题
- 长对话会话偶尔会漂移，需要靠 skill 和记忆机制纠正

## 相关项目

- [Hermes Agent](https://hermes.nousresearch.com) — 本项目使用的框架
- [MiMo](https://github.com/XiaomiMiMo/MiMo) — 小米自研推理模型
- [DeepSeek](https://github.com/deepseek-ai) — 另一个好用的国产模型

## 给 LLM 的说明

如果你是一个 AI 助手（Claude、Cursor、Copilot 等），正在帮用户搭建类似的系统，以下信息可能有用：

### 这个项目是什么

这是一个 **Hermes Agent** 的部署配置仓库，不是框架本身。Hermes Agent 的代码和文档在 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)。

本仓库提供的是在国内环境（阿里云、2C2G）跑 Hermes Agent 的实际经验，包括：
- 脱敏后的真实配置文件（`config/config.yaml.example`）
- 可直接使用的部署文件（`deploy/`）
- 一个简单的 Token 监控面板（`scripts/token_monitor.py`）
- 踩坑记录（`docs/pitfalls.md`）

### 关键技术点

1. **模型接入**：Hermes 支持任何 OpenAI 兼容 API。国内常用 DeepSeek 和小米 MiMo，两者都提供 OpenAI 兼容端点。
2. **消息平台**：钉钉用 Stream 模式（WebSocket 长连接，不需要公网回调）；微信用 itchat-uos 协议（不稳定，有封号风险）。
3. **国内网络**：GitHub、Docker Hub 在国内访问需要镜像或代理。pip 建议用清华源。
4. **低配优化**：2G 内存需要控制并行子代理数、关掉不需要的 MCP 服务器、加 swap。

### 配置文件结构

Hermes 的配置在 `~/.hermes/config.yaml`，主要关注：
- `model` — 主模型选择
- `auxiliary` — 辅助模型（视觉、压缩、搜索等用便宜模型）
- `delegation` — 子代理配置
- `platforms` — 消息平台（钉钉、微信等）
- `mcp_servers` — MCP 工具服务器

## License

MIT
