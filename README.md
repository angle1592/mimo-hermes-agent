# 🐱 小珀 — 基于 MiMo V2.5-Pro 的 AI 自动化助手系统

基于 [Hermes Agent](https://hermes.nousresearch.com) 搭建的 7×24 运行的 AI 自动化助手，以小米 MiMo V2.5-Pro 作为主模型，接入微信和钉钉双平台。

一个真实运行的 AI Agent 生产环境案例，探索如何用 LLM 构建可持续、可扩展的个人 AI 助手系统。

## 解决的核心痛点

传统 AI 助手的使用存在三个关键瓶颈：

**1. 上下文割裂** — 每次对话都是独立的，无法积累项目知识、用户偏好和历史决策。当你提到"上次那个项目"，AI 完全不知道你在说什么。

**2. 工具孤岛** — AI 只能对话，无法操作文件、执行代码、调用 API、管理日程。需要人工在 AI 和工具之间反复搬运信息。

**3. 单线程瓶颈** — 复杂任务（如"帮我做一份技术调研报告"）需要多步推理、信息收集、分析综合，单一模型串行处理既慢又容易丢失上下文。

小珀通过 **持久记忆 + 工具调用 + 多 Agent 协作** 三位一体解决这些问题。

## 核心逻辑流

```
用户消息（微信/钉钉）
    │
    ▼
┌─────────────────────────────────┐
│   Gateway（消息路由层）           │
│   ├── 钉钉 Stream Mode          │
│   └── 微信 itchat-uos           │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│   主 Agent（MiMo V2.5-Pro）     │
│   ├── 加载持久记忆               │
│   │   ├── 用户画像               │
│   │   ├── 项目上下文              │
│   │   └── 历史会话摘要            │
│   ├── 加载匹配的 Skill           │
│   └── 决策：直接回答 or 委派子任务 │
└──────┬──────────────┬───────────┘
       │              │
    直接回答      ┌────▼────────────────┐
       │         │  子 Agent 委派层       │
       │         │  ┌──────────────────┐ │
       │         │  │ 研究 Agent (web) │ │
       │         │  │ 代码 Agent (term)│ │
       │         │  │ 分析 Agent (file)│ │
       │         │  └──────────────────┘ │
       │         │  支持并行执行 + 嵌套委派 │
       │         └────┬────────────────┘
       │              │
       ▼              ▼
┌─────────────────────────────────┐
│   工具执行层                      │
│   ├── 终端（shell 命令、git）     │
│   ├── 文件系统（读写、搜索）      │
│   ├── 浏览器（Playwright MCP）   │
│   ├── Web 搜索（DuckDuckGo）     │
│   ├── SQLite 数据库              │
│   └── 定时任务引擎（cron）        │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│   响应 + 记忆更新                 │
│   ├── 格式化输出（适配平台）       │
│   ├── 更新持久记忆               │
│   └── 保存会话到 state.db        │
└─────────────┬───────────────────┘
              │
              ▼
        用户收到回复（微信/钉钉）
```

### 多 Agent 协作模式

面对复杂任务，主 Agent 会自动拆解并委派：

**示例：「帮我调研 MiMo 模型的技术特点并写一份报告」**

```
主 Agent（MiMo V2.5-Pro）
    │
    ├─→ 子 Agent 1（DeepSeek V4 Pro）
    │   任务：搜索 MiMo 技术论文和评测
    │   工具：web_search, web_extract
    │   输出：技术要点摘要
    │
    ├─→ 子 Agent 2（DeepSeek V4 Pro）
    │   任务：分析定价策略和竞品对比
    │   工具：web_search, terminal（数据计算）
    │   输出：对比分析表
    │
    ├─→ 子 Agent 3（DeepSeek V4 Pro）
    │   任务：查询实际 Token 使用数据
    │   工具：terminal（SQLite 查询 state.db）
    │   输出：历史消耗统计
    │
    └─→ 主 Agent 综合所有子任务结果
        生成：完整调研报告
```

### 长链推理链路

当任务需要多步推理时，系统支持深度推理链：

```
用户：「部署有个 bug，帮我排查」
    │
    ├─ Step 1：读取错误日志 → 提取关键异常
    ├─ Step 2：定位相关源码文件 → 分析逻辑
    ├─ Step 3：搜索 Stack Overflow / GitHub Issues
    ├─ Step 4：生成修复方案 → 写入文件
    ├─ Step 5：运行测试验证
    └─ Step 6：提交 commit + 生成变更说明
```

每一步的输出作为下一步的输入，推理链可长达 10+ 步，中间结果持久化在会话上下文中。

## 实际使用场景

| 场景 | 触发方式 | 处理流程 |
|------|---------|---------|
| 每日自动汇报 | 定时任务 5:30 | 查询日历/待办 → 生成早安推送 |
| 代码审查 | 发送 GitHub PR 链拉取 diff → 逐文件分析 → 生成评审意见 |
| 技术调研 | 自然语言描述需求 → 多 Agent 并行搜索 → 综合生成报告 |
| 文件处理 | 发送 PDF/文档 → OCR 提取 → 分析总结 |
| 系统运维 | SSH 到服务器 → 执行命令 → 返回结果 |

## Token 使用情况

实际生产环境中的 Token 消耗数据：

| 指标 | 数值 |
|------|------|
| 日均消耗 | 1,000~3,000 万 tokens |
| 单次会话 | 200~800 万 tokens |
| 缓存命中率 | 97%+ |
| 月均成本 | ¥12~24 |

## 技术栈

| 组件 | 说明 |
|------|------|
| 主模型 | Xiaomi MiMo V2.5-Pro（主力推理） |
| 辅助模型 | DeepSeek V4 Pro / Flash（子代理、辅助任务） |
| 框架 | Hermes Agent v0.12.0 |
| 平台 | 微信 + 钉钉 |
| MCP 工具 | Playwright（浏览器）、Sequential Thinking（推理）、SQLite |
| 监控 | 自建 Token 用量面板（Nginx + systemd） |
| 部署 | Alibaba Cloud Linux，2 vCPU / 2GB RAM |

## 项目结构

```
├── README.md                          # 本文件
├── config/
│   └── config.example.yaml            # 配置模板（含详细注释）
├── docs/
│   ├── deployment-guide.md            # 完整部署指南
│   └── mimo-integration.md            # MiMo 集成实践文档
├── scripts/
│   └── token_monitor.py               # Token 用量监控面板
├── xiao-po-skill.md                   # 小珀角色设定 Skill
└── source-patches-skill.md            # 源码修改管理 Skill
```

## 快速开始

详见 [部署指南](docs/deployment-guide.md)

```bash
# 安装 Hermes Agent
pip install hermes-agent
hermes init

# 配置 MiMo 模型
export XIAOMI_API_KEY="your-api-key"
# 编辑 ~/.hermes/config.yaml，参考 config/config.example.yaml

# 启动
hermes gateway start

# 启动 Token 监控面板
python3 scripts/token_monitor.py
```

## 相关链接

- [Hermes Agent 官方文档](https://hermes.nousresearch.com)
- [小米 MiMo 模型](https://github.com/XiaomiMiMo/MiMo)
- [MiMo V2.5-Pro 集成实践](docs/mimo-integration.md)
