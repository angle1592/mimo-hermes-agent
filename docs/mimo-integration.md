# MiMo V2.5-Pro 集成笔记

记录将小米 MiMo V2.5-Pro 接入 Hermes Agent 的实际经验。

## 基本信息

| 项目 | 值 |
|------|-----|
| 模型 | mimo-v2.5-pro |
| 上下文窗口 | 1M tokens |
| API 协议 | OpenAI 兼容 |
| API 端点 | `https://api.xiaomimimo.com/v1` |
| 官方定价 | [pricing.md](https://platform.xiaomimimo.com/static/docs/pricing.md) |

## 接入方式

MiMo 通过 OpenAI 兼容接口接入，Hermes 原生支持。在 config.yaml 中配置：

```yaml
models:
  main:
    provider: xiaomi
    model: mimo-v2.5-pro
    api_key_env: XIAOMI_API_KEY
```

API Key 在 [MiMo 开放平台](https://platform.xiaomimimo.com/) 申请。

## 定价（截至 2026 年 5 月）

以官方页面为准，以下是写作时的参考数据（国内定价，每百万 tokens）：

| 场景 | 输入（缓存命中） | 输入（缓存未命中） | 输出 |
|------|-----------------|-------------------|------|
| ≤256K 上下文 | ¥1.40 | ¥7.00 | ¥21.00 |
| 256K-1M 上下文 | ¥2.80 | ¥14.00 | ¥42.00 |

> 注意：MiMo 的输出定价较高。对比 DeepSeek V4 Pro（优惠期间输出约 ¥6/1M），MiMo 的输出成本约为其 3.5 倍。选择模型时需要综合考虑能力、速度和成本。

## 与 DeepSeek V4 Pro 的实际对比

| 维度 | MiMo V2.5-Pro | DeepSeek V4 Pro |
|------|---------------|-----------------|
| 推理能力 | 不错，特别是中文语境 | 强，综合表现稳定 |
| 工具调用 | 偶尔不稳定 | 稳定 |
| 输出定价 | 较高（¥21/1M） | 较低（优惠期 ¥6/1M） |
| 上下文 | 1M | 1M |
| 缓存支持 | 支持，命中率高时成本显著降低 | 支持 |

我的实际用法：MiMo 做主模型处理推理任务，DeepSeek Flash 做子代理处理并行任务。这样在能力和成本之间取得平衡。

## Token 消耗参考

不同任务类型的实际消耗差异很大：

- 简单问答：5,000~20,000 tokens
- 代码审查：50,000~200,000 tokens
- 多步研究报告：200,000~800,000 tokens
- 多 Agent 委派：500,000~2,000,000 tokens

缓存命中率在实际使用中可以达到 97% 以上，这对控制成本很关键。

## 注意事项

- MiMo 的 API 端点在国内，延迟比 DeepSeek 略高
- 工具调用（function calling）偶尔会有格式不规范的情况
- 定价和优惠会变，以官方页面为准
