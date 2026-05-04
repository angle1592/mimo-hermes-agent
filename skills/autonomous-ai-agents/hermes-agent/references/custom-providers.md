# Adding Custom OpenAI-Compatible Providers

When a provider uses OpenAI-compatible API format but isn't built into Hermes, add it manually.

## Config Format

In `~/.hermes/config.yaml`, add to the `providers` dict:

```yaml
providers:
  <provider-name>:
    base_url: https://api.example.com/v1    # Required: OpenAI-compatible base URL
    key_env: EXAMPLE_API_KEY                 # Env var name in ~/.hermes/.env
    name: Example Provider                   # Display name
    # Optional fields:
    # api_mode: chat_completions             # Force API mode
    # model: default-model-name              # Default model
    # context_length: 128000                 # Max context window
    # request_timeout_seconds: 300           # Request timeout
```

Then add the API key to `~/.hermes/.env`:
```
EXAMPLE_API_KEY=sk-xxxxx
```

## Usage

```bash
hermes -m <model-id> --provider <provider-name>
# or in session:
/model <model-id>
```

## Known Custom Providers on This Server

### SenseNova (商汤日日新)
- Provider name: `sensenova`
- Base URL: `https://token.sensenova.cn/v1`
- Key env: `SENSENOVA_API_KEY`
- Token Plan: Free public beta (as of 2026-05)

| Model ID | Type | Rate Limit | Notes |
|----------|------|------------|-------|
| `sensenova-6.7-flash-lite` | Multimodal agent | 1500 calls/5h | Reasoning model, output goes to `reasoning` field first |
| `sensenova-u1-fast` | Infographic gen | 1500 calls/5h | Image generation focused |
| `deepseek-v4-flash` | Chat | 150 calls/5h | DS V4 Flash hosted on SenseNova |

**API Quirk:** `sensenova-6.7-flash-lite` is a reasoning model. It generates thinking content in the `message.reasoning` field before producing `message.content`. With low `max_tokens`, the reasoning consumes the entire budget and `content` is empty. Solution: use higher max_tokens (500+). This is standard OpenAI-compatible format with an extra `reasoning` field in the response.

**Test command:**
```bash
curl -s https://token.sensenova.cn/v1/chat/completions \
  -H "Authorization: Bearer $SENSENOVA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"sensenova-6.7-flash-lite","messages":[{"role":"user","content":"1+1=?"}],"max_tokens":500}'
```

## Pitfalls

- **`providers: {}` is the default** — the section exists but is empty in fresh installs
- **key_env vs api_key** — use `key_env` to reference an env var name (recommended, keeps secrets in .env). Use `api_key` only for inline values (less secure).
- **base_url must include `/v1`** — most OpenAI-compatible APIs expect the full path
- **Config uses YAML** — after editing, verify with `python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"` to catch syntax errors
- **Restart required** — provider changes need gateway restart (`hermes gateway restart`) or new CLI session
