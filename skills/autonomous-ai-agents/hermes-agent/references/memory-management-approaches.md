# Memory Management Approaches in Hermes Agent

## Built-in Memory (MEMORY.md / USER.md)

- **Storage:** `~/.hermes/memories/MEMORY.md` (2,200 chars) + `USER.md` (1,375 chars)
- **Tool actions:** `add`, `replace`, `remove` only — no cleanup/organize
- **CLI:** `hermes memory` has `setup`, `status`, `off`, `reset` — no cleanup command
- **Behavior:** Agent self-manages during conversations; consolidates when near capacity
- **No built-in auto-cleanup or scheduled organization feature**

## External Memory Providers (auto-manage)

These run alongside built-in memory (never replacing it). They auto-extract, deduplicate, and organize.

### Mem0 — Best for hands-off management
- Auto-extracts facts at session end (via `sync_turn()`)
- Semantic search + automatic deduplication + reranking
- Server-side LLM fact extraction
- Provides 3 tools: `mem0_profile` (get all), `mem0_search` (semantic search), `mem0_conclude` (store verbatim fact)
- Has circuit breaker: pauses API calls after 5 consecutive failures (120s cooldown)
- Cost: Mem0 Cloud pricing

**Setup (non-interactive — tested 2026-05-14):**

```bash
# 1. Install the SDK
pip install mem0ai

# 2. Create config file
cat > ~/.hermes/mem0.json << 'EOF'
{
  "api_key": "YOUR_MEM0_API_KEY",
  "user_id": "hermes-user",
  "agent_id": "hermes",
  "rerank": true
}
EOF

# 3. Activate the provider
hermes config set memory.provider mem0

# 4. Verify
hermes memory status
# Should show: "mem0 ← active" with "Status: available ✓"
```

**Config precedence:** Environment variables (`MEM0_API_KEY`, `MEM0_USER_ID`, `MEM0_AGENT_ID`) provide defaults; `~/.hermes/mem0.json` overrides individual keys. API key is required (from either source).

**How it works:** Built-in memory (MEMORY.md/USER.md) runs in parallel — Mem0 does NOT replace it. On each conversation turn, `sync_turn()` sends user+assistant messages to Mem0's API for server-side fact extraction (non-blocking, threaded). At session start, `queue_prefetch()` does a semantic search to pre-load relevant memories. Gateway passes `user_id` from the platform adapter for per-user scoping.

**Pitfall: `hermes memory setup` is interactive-only.** The wizard has no CLI arguments — you must either use the interactive TUI or configure manually as shown above.

### Honcho — Context + dialectic reasoning
- Auto-extracts memories on session end
- Two-layer context injection: base layer + dialectic supplement
- Cold-start vs warm prompts based on existing context
- Requires: API key from app.honcho.dev
- Config: `recallMode`, `contextCadence`, `dialecticCadence`, `writeFrequency`

### Hindsight — Knowledge graph + auto-retain
- `auto_retain: true` — automatically retain conversation turns
- `auto_recall: true` — automatically recall before each turn
- Entity extraction and cross-memory synthesis (`hindsight_reflect`)
- Modes: cloud or local
- Config: `memory_mode: hybrid`, `retain_async: true`

### OpenViking (ByteDance) — Filesystem-style hierarchy
- Automatic memory extraction on session commit
- 6 categories: profile, preferences, entities, events, cases, patterns
- Tiered retrieval with automatic deduplication

### Holographic — Contradiction detection
- `contradict` — automated detection of conflicting facts
- Local storage, no API key needed

### Others: ByteRover, RetainDB, Supermemory
- Various capabilities (knowledge graphs, semantic search, etc.)

## Cron-based Memory Cleanup (DIY)

The user had a cron job that ran daily to organize memory. Key findings:

- **Problem:** `skip_memory=True` is hardcoded in `cron/scheduler.py` — the `memory` tool is always disabled in cron
- **Workaround that sometimes works:** Model uses `read_file`/`write_file` to directly access memory files
- **Why it's unreliable:** LLM non-determinism — the model may switch between file access and tool access between runs
- **Timeline:** Worked Apr 29 → May 12, broke May 13 (same code, no config change)

### If user wants cron-based memory maintenance:

Option 1: Rewrite prompt to explicitly instruct `read_file`/`write_file` on `~/.hermes/memories/MEMORY.md` and `USER.md`. Still unreliable.

Option 2: Use a reminder cron job that tells the user to do cleanup manually in an interactive session.

Option 3: Patch `skip_memory=True` out of `cron/scheduler.py` (requires user approval + hermes-source-patches).

Option 4: Use an external memory provider (Mem0, Honcho, Hindsight) that handles cleanup automatically — no cron needed.

## Recommendation

For users who want hands-off memory management:
1. **Short-term:** Set up Mem0 or Hindsight via `hermes memory setup`
2. **Long-term:** Wait for Hermes to add built-in cognitive memory operations (feature request #509 on GitHub)
