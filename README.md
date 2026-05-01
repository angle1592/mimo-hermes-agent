# 🐱 小珀 — 基于 MiMo V2.5-Pro 的 AI 自动化助手系统

基于 [Hermes Agent](https://hermes.nousresearch.com) 搭建的 7×24 运行的 AI 自动化助手，以小米 MiMo V2.5-Pro 作为主模型，接入微信和钉钉双平台。

## 核心能力

- **多 Agent 子任务委派**：复杂任务自动拆解并分配给专业子代理
- **跨会话持久记忆**：记住用户偏好和项目上下文
- **自定义技能编排**：可复用的 Skill 系统
- **实时 Token 用量监控**：基于 DeepSeek 官方定价的 Web 面板
- **定时任务系统**：cron 驱动的自动化工作流
- **多平台接入**：微信 + 钉钉双平台实时通信

## Token 使用情况

日均消耗约 1000~3000 万 Token，单次会话处理 200~800 万 Token，缓存命中率 97% 以上，属于重度 Agentic 场景的真实生产使用。

## 技术栈

| 组件 | 说明 |
|------|------|
| 主模型 | Xiaomi MiMo V2.5-Pro（主力推理） |
| 辅助模型 | DeepSeek V4 Pro / Flash（子代理、辅助任务） |
| 框架 | Hermes Agent v0.12.0 |
| 平台 | 微信 + 钉钉 |
| 监控 | 自建 Token 用量面板（Nginx + systemd） |
| 部署 | Alibaba Cloud Linux，2 vCPU / 2GB RAM |

## 文件说明

- `xiao-po-skill.md` — 小珀角色设定 Skill
- `source-patches-skill.md` — 源码修改管理 Skill（含 patch 文件和恢复脚本）
- `token_monitor_server.py` — Token 用量监控面板源码（待补充）

## 相关链接

- [Hermes Agent 官方文档](https://hermes.nousresearch.com)
- [小米 MiMo 模型](https://github.com/XiaomiMiMo/MiMo)
