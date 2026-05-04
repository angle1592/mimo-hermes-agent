# Xiaomi MiMo 定价参考

> 来源: https://platform.xiaomimimo.com/docs/en-US/pricing
> 最后更新: 2026-05-01

## Token Plan 积分消耗比率

积分不等于Token！Pro模型2倍消耗：

| 模型 | 积率 |
|------|------|
| MiMo-V2.5-Pro / V2-Pro | 2x（1 token = 2 积分） |
| MiMo-V2.5 / V2-Omni | 1x |
| TTS 系列 | 0x（限时免费） |

## 国内定价（CNY / 百万 Token，input ≤ 256K）

| 模型 | 缓存命中 | 缓存未命中 | 输出 |
|------|---------|-----------|------|
| mimo-v2.5-pro | 1.40 | 7.00 | 21.00 |
| mimo-v2.5 | 0.56 | 2.80 | 14.00 |
| mimo-v2-flash | 0.07 | 0.70 | 2.10 |

256K-1M上下文区间：以上价格x2。

## 海外定价（USD / 百万 Token，input ≤ 256K）

| 模型 | 缓存命中 | 缓存未命中 | 输出 |
|------|---------|-----------|------|
| mimo-v2.5-pro | 0.20 | 1.00 | 3.00 |
| mimo-v2.5 | 0.08 | 0.40 | 2.00 |
| mimo-v2-flash | 0.01 | 0.10 | 0.30 |

## 模型名标准化

Hermes数据库中可能出现的变体需要统一映射：
- mimo-v2-pro 映射到 mimo-v2.5-pro
- xiaomi/mimo-v2.5 映射到 mimo-v2.5

## 100T激励计划

- URL: https://100t.xiaomimimo.com
- 时间: 2026/4/28 到 5/28
- 申请通过最高获Max档位（16亿Credits）
