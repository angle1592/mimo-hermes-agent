# Hermes Agent 国内环境部署经验

用 [Hermes Agent](https://hermes.nousresearch.com) 搭了一个个人 AI 助手，跑了大半年，接入微信和钉钉。模型换过几次（DeepSeek → MiMo），配置和踩坑经验记在这里，供参考。

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
# 安装
pip install hermes-agent
hermes init

# 配置模型（以 MiMo 为例，换其他模型同理）
# 编辑 ~/.hermes/config.yaml，参考 config/config.example.yaml
hermes config set models.main.provider xiaomi
hermes config set models.main.model mimo-v2.5-pro

# 启动网关
hermes gateway start
```

完整的配置说明见 [config/config.example.yaml](config/config.example.yaml)（含详细注释）。

## 当前配置

| 组件 | 选型 | 备注 |
|------|------|------|
| 框架 | Hermes Agent | 开源 Agent 框架 |
| 主模型 | MiMo V2.5-Pro | 小米，通过 OpenAI 兼容接口接入 |
| 辅助模型 | DeepSeek V4 Pro / Flash | 子代理和辅助任务 |
| 消息平台 | 微信 + 钉钉 | 微信用 itchat-uos，钉钉用 Stream Mode |
| MCP 工具 | Playwright、SQLite、Sequential Thinking | 浏览器自动化、数据存储、分步推理 |
| 部署 | Alibaba Cloud Linux | 2 vCPU / 2GB RAM |

模型不是固定的。之前用 DeepSeek 做主力，现在换成了 MiMo，以后可能还会变。Hermes 支持任何 OpenAI 兼容的 API，换模型只需改配置。

## 模型切换经验

不同模型各有特点，没有银弹。以下是我用过的：

| 模型 | 适合 | 不适合 |
|------|------|--------|
| MiMo V2.5-Pro | 推理、代码、中文理解 | 工具调用偶尔不稳定 |
| DeepSeek V4 Pro | 综合能力强、工具调用稳定 | 价格稍高 |
| DeepSeek V4 Flash | 速度快、便宜 | 复杂推理弱 |

实际使用中，主模型和辅助模型搭配效果比单一模型好。比如用 MiMo 做主力推理，子代理用 DeepSeek 处理并行任务。

## 实际跑起来的一些数据

仅供参考，不同使用强度差异很大：

- 日均 Token 消耗：1,000~3,000 万（高强度日会更多）
- 缓存命中率：97% 以上（Hermes 的 context caching 机制）
- 月成本：十几到二十几块钱（MiMo 定价比较便宜）
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
│   └── config.example.yaml        # 配置模板（含注释）
├── docs/
│   ├── deployment-guide.md        # 部署步骤
│   └── mimo-integration.md        # MiMo 接入笔记
├── scripts/
│   └── token_monitor.py           # Token 用量监控（Web 面板）
├── xiao-po-skill.md               # 一个自定义角色 skill 示例
└── source-patches-skill.md        # 源码修改管理 skill 示例
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

## License

MIT
