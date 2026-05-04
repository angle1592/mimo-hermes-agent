# SenseNova (商汤日日新) Provider Integration

**Date:** 2026-05-03
**Platform:** platform.sensenova.cn
**Status:** Token Plan 公测 (free, limited)

## API Details

- **Base URL:** `https://token.sensenova.cn/v1`
- **Auth:** Bearer token (API key from platform console)
- **Format:** OpenAI-compatible (chat/completions)
- **Key prefix:** `sk-`

## Available Models (Free Tier)

| Model ID | Description | Rate Limit |
|----------|-------------|------------|
| `sensenova-6.7-flash-lite` | Multimodal agent model, reasoning mode | 1500 calls / 5h |
| `sensenova-u1-fast` | Infographic generation | 1500 calls / 5h |
| `deepseek-v4-flash` | DeepSeek V4 Flash (hosted by SenseNova) | 150 calls / 5h |

## Key Behavior

- **Reasoning model by default** — `sensenova-6.7-flash-lite` generates reasoning content in `message.reasoning` field before actual content in `message.content`. With low `max_tokens` (e.g. 100-200), reasoning consumes all tokens and content is empty. Set `max_tokens ≥ 500` for reliable content output.
- **OpenAI SDK compatible** — Just change `base_url`. No custom SDK needed.
- **No `deepseek-v4-pro`** — Free tier only has flash, not pro.

## Hermes Config

### .env
```
SENSENOVA_API_KEY=sk-...
```

### config.yaml
```yaml
providers:
  sensenova:
    base_url: https://token.sensenova.cn/v1
    key_env: SENSENOVA_API_KEY
    name: SenseNova
```

### Usage as auxiliary provider (DEPRECATED for DeepSeek models — see Quality Assessment)
```yaml
# DON'T: SenseNova's DeepSeek quality is worse than official
auxiliary:
  vision:
    provider: sensenova        # ❌ lower quality
    model: deepseek-v4-flash

# DO: Use official DeepSeek for DeepSeek models
auxiliary:
  vision:
    provider: deepseek         # ✅ official API
    model: deepseek-v4-flash

# SenseNova is still fine for its own proprietary models:
auxiliary:
  vision:
    provider: sensenova
    model: sensenova-6.7-flash-lite  # ✅ SenseNova's own model
```

## Quality Assessment (2026-05)

**SenseNova's hosted DeepSeek models have noticeably lower quality than official DeepSeek API.** After extended use, user concluded the output quality is unacceptable for auxiliary tasks (vision, web extraction, session search, etc.) and switched all auxiliary providers back to official DeepSeek. SenseNova's free tier is still useful for the proprietary `sensenova-6.7-flash-lite` model, but don't use it as a DeepSeek proxy for quality-sensitive work.

Current config state (post-switch):
- Main model: `xiaomi/mimo-v2.5-pro` (unchanged)
- Auxiliary: `deepseek/deepseek-v4-flash` (official API, was `sensenova/deepseek-v4-flash`)
- Compression: `deepseek/deepseek-v4-pro` (was already official)

## Pitfalls

- **API key format** — Keys start with `sk-` (looks like OpenAI keys). Don't confuse with DeepSeek keys.
- **Reasoning consumes tokens** — The model does chain-of-thought reasoning by default. A simple "1+1=?" uses ~450 tokens total (41 prompt + 446 completion, mostly reasoning). Factor this into rate limit planning.
- **No streaming test** — Didn't test streaming (SSE) support. May need investigation.
- **Content empty with low max_tokens** — If `finish_reason: "length"` and content is empty, increase `max_tokens`. The reasoning phase uses tokens first.
- **Rate limits are per-model** — Each model has its own 5h window. `sensenova-6.7-flash-lite` and `deepseek-v4-flash` have separate limits.
- **Console registration** — Requires Chinese phone number for SMS verification at platform.sensenova.cn.
