# 🤖 MiMo + Hermes Agent 自动化助手系统

基于 [Xiaomi MiMo V2.5-Pro](https://platform.xiaomimimo.com) 和 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 搭建的 7×24 自动化 AI 助手系统，接入微信和钉钉平台，覆盖日常工作流的全自动化。

## 🏗️ 系统架构

```
用户消息（微信/钉钉）
    ↓
Hermes Agent Gateway（消息路由 + 会话管理）
    ↓
AIAgent（主模型: MiMo V2.5-Pro）
    ├── 多 Agent 子任务委派（deepseek-v4-pro）
    ├── 持久记忆系统（跨会话）
    ├── 自定义技能编排（Skills）
    ├── 定时任务调度（Cron）
    ├── MCP 服务器集成（Playwright / SQLite）
    └── Token 用量实时监控面板
```

## ✨ 核心能力

| 能力 | 说明 |
|------|------|
| **多平台接入** | 微信（iLink Bot API）+ 钉钉（Stream Mode）7×24 在线 |
| **多 Agent 协作** | 主代理委派子任务给专业子代理，支持并行执行 |
| **持久记忆** | 跨会话记忆用户偏好、环境信息、项目上下文 |
| **自定义技能** | 将复杂工作流封装为可复用的 Skill 文档 |
| **定时任务** | Cron 调度，自动执行日报、监控、推荐等任务 |
| **Token 监控** | 实时 Web 面板，按模型/会话/来源统计用量和费用 |
| **MCP 集成** | Playwright 浏览器自动化、SQLite 数据分析 |
| **语音合成** | MiMo V2.5-TTS 中文语音输出 |

## 📊 使用规模

- **主模型**：MiMo V2.5-Pro（Token Plan SGP）
- **辅助模型**：DeepSeek V4-Pro / V4-Flash
- **单次会话 Token 消耗**：约 200~800 万 Token
- **日均 Token 消耗**：约 1000~3000 万 Token
- **缓存命中率**：97%+
- **累计会话数**：50+（持续增长中）
- **运行时间**：7×24 不间断

## 📁 项目结构

```
├── README.md                    # 本文件
├── token_monitor/               # Token 用量监控面板
│   └── server.py                # Python HTTP 服务 + 前端
├── skills/                      # 自定义技能示例
│   └── hermes-source-patches/   # 源码修改管理 skill
├── config/                      # 配置示例
│   └── config.example.yaml      # Hermes Agent 配置模板
└── docs/                        # 文档
    └── setup-guide.md           # 部署指南
```

## 🚀 Token 监控面板

实时 Web 面板，展示：

- 总 Token 数（含缓存命中/未命中）
- 缓存命中率
- 按模型分类的用量和费用（人民币/美元双币种）
- 按日期分组的会话记录，支持搜索/筛选/排序
- DeepSeek + Xiaomi MiMo 双厂商定价
- 每 10 秒自动刷新

## 🔧 技术栈

- **Agent 框架**：Hermes Agent（Python，OpenAI 兼容 API）
- **主模型**：Xiaomi MiMo V2.5-Pro（1M 上下文窗口）
- **消息平台**：微信 iLink Bot API、钉钉 Stream SDK
- **监控面板**：Python HTTP Server + 原生 HTML/JS
- **数据库**：SQLite（会话 + Token 统计）
- **部署**：Alibaba Cloud Linux、Nginx、systemd

## 📝 License

MIT
