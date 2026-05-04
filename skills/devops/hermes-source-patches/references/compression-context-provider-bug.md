# Compression Model Context Resolution Bug

**Status**: Known bug, workaround in place (2026-05-05)
**File**: `run_agent.py` line ~2628 (`_check_compression_feasibility()`)
**Hermes version**: v0.12.0

## Bug Description

`_check_compression_feasibility()` passes the **main model's provider** instead of the **compression model's provider** to `get_model_context_length()`:

```python
# Line 2628 — BUG
aux_context = get_model_context_length(
    aux_model,                                    # "deepseek-v4-pro"
    base_url=aux_base_url,                        # "https://api.deepseek.com/v1/"
    api_key=aux_api_key,
    config_context_length=getattr(self, "_aux_compression_context_length_config", None),
    provider=getattr(self, "provider", ""),       # ← BUG: main model's provider ("xiaomi"), not "deepseek"
)
```

## Why It Matters

When `provider="xiaomi"` is passed for model `deepseek-v4-pro`:

1. `models_dev("xiaomi", "deepseek-v4-pro")` → **None** (deepseek-v4-pro isn't a Xiaomi model)
2. Falls through to OpenRouter metadata → **131,000** (WRONG — OpenRouter has stale/incorrect data)
3. Never reaches hardcoded defaults (`"deepseek-v4-pro": 1_000_000`)

If the correct `provider="deepseek"` were passed, step 1 would return `1,000,000` from models.dev.

## How to Verify

```python
cd /usr/local/lib/hermes-agent && python3 -c "
import sys; sys.path.insert(0, '.')
from agent.model_metadata import get_model_context_length

# Bug: main model provider
print(get_model_context_length('deepseek-v4-pro', base_url='https://api.deepseek.com/v1/', provider='xiaomi'))
# → 131000

# Correct: compression model provider
print(get_model_context_length('deepseek-v4-pro', base_url='https://api.deepseek.com/v1/', provider='deepseek'))
# → 1000000
```

## Workaround (config.yaml)

Add explicit `context_length` to the compression config (highest priority in resolution chain):

```yaml
auxiliary:
  compression:
    provider: deepseek
    model: deepseek-v4-pro
    context_length: 1000000    # ← workaround for provider bug
```

## Proper Fix (source patch)

Change line ~2628 in `run_agent.py`:

```python
# BEFORE (bug):
provider=getattr(self, "provider", ""),

# AFTER (fix):
provider=_aux_cfg_provider or getattr(self, "provider", ""),
```

`_aux_cfg_provider` is already resolved at line 2603 from `_resolve_task_provider_model("compression")` and contains the compression model's actual provider ("deepseek"). The fallback to `self.provider` handles edge cases where aux provider resolution fails.

## Root Cause Chain

1. `_check_compression_feasibility()` doesn't have the aux model's provider readily available in the right variable
2. `getattr(self, "provider", "")` was used as a shortcut — works fine when main and aux share the same provider, breaks when they differ
3. OpenRouter's metadata for `deepseek-v4-pro` reports `context_length: 131000` — this is **not a bug on OpenRouter's side**. OpenRouter's free tier (pricing: $0/$0) genuinely caps deepseek-v4-pro at 131K context. The paid tier (deepseek-v4-flash) has the full 1M. The problem is that Hermes falls back to OpenRouter's free-tier metadata instead of the official DeepSeek models_dev entry.

## OpenRouter Free Tier Context Caps

OpenRouter hosts free/community tiers of popular open-source models with reduced context windows. These show up in the `/api/v1/models` metadata with `pricing.prompt: "0"` and capped `context_length`. Examples (as of 2026-05):

| Model | OpenRouter Free Tier | Official API |
|-------|---------------------|-------------|
| deepseek-v4-pro | 131,000 | 1,000,000 |
| deepseek-v4-flash | 1,048,576 (paid) | 1,000,000 |

When `get_model_context_length()` falls through to OpenRouter metadata (step 6 in resolution chain), it may pick up these capped values instead of the model's true context window.
