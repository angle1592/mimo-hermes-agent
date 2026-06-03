# Model Pricing Reference (Shared)

Canonical pricing data used by `scripts/token_monitor.py` and documented in `skills/hermes-token-monitor/SKILL.md`.

## Current Pricing (per 1M tokens, USD)

| Model | Cache Hit | Cache Miss | Output | Vendor | Notes |
|---|---|---|---|---|---|
| deepseek-v4-flash | $0.0028 | $0.14 | $0.28 | DeepSeek | |
| deepseek-v4-pro | $0.003625 | $0.435 | $0.87 | DeepSeek | 75% off until 2026-05-31 |
| mimo-v2.5-pro | $0.20 | $1.00 | $3.00 | Xiaomi | 256K-1M = 2x |
| mimo-v2.5 | $0.08 | $0.40 | $2.00 | Xiaomi | 256K-1M = 2x |
| mimo-v2-flash | $0.01 | $0.10 | $0.30 | Xiaomi | <=256K only |

## Model Name Aliases

DB may store variant names. Normalization map:

| DB raw name | Canonical name |
|---|---|
| `deepseek-chat` | `deepseek-v4-flash` |
| `deepseek-reasoner` | `deepseek-v4-flash` |
| `mimo-v2-pro` | `mimo-v2.5-pro` |
| `xiaomi/mimo-v2.5` | `mimo-v2.5` |

## CNY Display Values (per 1M tokens)

| Model | Cache Hit | Cache Miss | Output |
|---|---|---|---|
| mimo-v2.5-pro | 1.40 | 7 | 21 |
| mimo-v2.5 | 0.56 | 2.80 | 14 |
| mimo-v2-flash | 0.07 | 0.70 | 2.10 |

## Sources

- DeepSeek: https://api-docs.deepseek.com/quick_start/pricing
- MiMo: https://platform.xiaomimimo.com/docs/en-US/pricing
- Exchange rate: `USD_TO_CNY = 6.85` (check periodically via `https://open.er-api.com/v6/latest/USD`)
