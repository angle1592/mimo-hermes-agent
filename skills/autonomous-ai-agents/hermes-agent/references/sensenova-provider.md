# SenseNova (商汤日日新) as Hermes Provider

## Overview

SenseNova provides OpenAI-compatible API at `https://token.sensenova.cn/v1`. Token Plan (公测) is free with rate limits.

## Config

```yaml
# ~/.hermes/config.yaml
providers:
  sensenova:
    base_url: https://token.sensenova.cn/v1
    key_env: SENSENOVA_API_KEY
    name: SenseNova
```

```bash
# ~/.hermes/.env
SENSENOVA_API_KEY=sk-xxxxx
```

## Available Models (Token Plan, 2026-05)

| Model ID | Description | Rate Limit |
|----------|-------------|------------|
| `sensenova-6.7-flash-lite` | Multimodal agent model, reasoning mode | 1500 calls/5h |
| `sensenova-u1-fast` | Infographic generation | 1500 calls/5h |
| `deepseek-v4-flash` | DeepSeek V4 Flash hosted by SenseNova | 150 calls/5h |

## Model Quirks

### Reasoning Content in Separate Field

SenseNova models return reasoning in `message.reasoning` field, NOT in `message.content`. The `content` field may be empty if `max_tokens` is too low (reasoning consumes all tokens before content generation).

**Implication for Hermes**: Hermes stores reasoning in `assistant_msg["reasoning"]` — this should work correctly since the OpenAI SDK parses it. But verify that Hermes's reasoning display (`display.show_reasoning`) handles this format.

**Test result** (sensenova-6.7-flash-lite, max_tokens=500):
- Simple question "1+1=?" → 1372 chars reasoning, then "1+1=2。" in content
- Reasoning is in English even for Chinese questions
- `finish_reason: "stop"` on success, `"length"` when max_tokens exhausted

### Token Consumption

Reasoning-heavy models consume more tokens. A simple "1+1=?" used 487 tokens (41 prompt + 446 completion, mostly reasoning). Budget accordingly.

## Integration Notes

- Platform page: `platform.sensenova.cn`
- Docs: `platform.sensenova.cn/docs`
- Console (API keys): `platform.sensenova.cn` → 控制台
- Registration: phone number + SMS verification
- Compatible with OpenAI SDK: just change `base_url`

## Pitfalls

- **deepseek-v4-pro NOT available** on Token Plan — only flash version. Keep complex tasks (delegation, compression) on official DeepSeek provider.
- **Rate limits are per-5-hour window**, not per-minute. High-frequency auxiliary tasks (session_search, etc.) may hit limits if many sessions run concurrently.
- **API key format**: starts with `sk-`, same format as OpenAI keys.
