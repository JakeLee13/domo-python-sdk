# Cost tracking

Every notebook that calls `llm.prompt()`, `llm.parallel()`, or `vector.embed()` accumulates token usage into a thread-safe global counter. Notebooks read the total at the end of a run, scope a block via context manager, or flush a row to a Domo dataset for cross-run cost analysis.

> See [ai-response-shape.md](ai-response-shape.md) for the underlying API response shape and why embedding tokens are estimated rather than measured.

## Quick start

```python
from domo_sdk import auth, llm, get_usage, reset_usage, track, flush_usage_to_dataset

auth(dev_token, client_id, client_secret)
reset_usage()  # Optional: clear the global counter at start of a run

llm.prompt("Summarize this transcript: ...")
llm.parallel(items, lambda x: llm.prompt(f"Classify: {x}"))

print(get_usage())
# {'input_tokens': 12044, 'output_tokens': 3201, 'reasoning_tokens': 0,
#  'embedding_tokens_estimated': 0, 'total_tokens': 15245,
#  'chat_calls': 47, 'embedding_calls': 0, 'elapsed_seconds': 38.2, ...}
```

## Three layers

### 1. Always-on global accumulator (zero-config)

Every chat and embedding call routes through `usage.record_call()`. You don't need to do anything to enable it — `get_usage()` returns the running total at any time.

```python
get_usage()        # snapshot of accumulated totals
reset_usage()      # zero out the counter (call at start of a notebook)
```

### 2. Scoped tracking with `track()` context manager

To measure cost of a specific block (e.g. a single phase of analysis), use `with track() as t:`. The context object exposes the *delta* — what happened inside the block. Tokens used inside the block are still counted in the global accumulator too.

```python
with track() as phase1:
    for item in dataset:
        llm.prompt(f"Extract entities from: {item}")
print(f"Phase 1: {phase1.chat_calls} calls, {phase1.total_tokens} tokens, {phase1.elapsed_seconds:.1f}s")

with track() as phase2:
    summary = llm.prompt("Aggregate all the extracted entities into a report")
print(f"Phase 2: {phase2.chat_calls} calls, {phase2.total_tokens} tokens")
```

Fields on the context object:
- `input_tokens`, `output_tokens`, `reasoning_tokens`, `embedding_tokens_estimated`
- `total_tokens` — sum of the four above
- `chat_calls`, `embedding_calls`
- `elapsed_seconds` — wall-clock for the block (not just API time)

### 3. Persistent flush to a Domo dataset

For cross-run cost analysis, flush the accumulated usage as a row in a Domo dataset. Call once at the end of a notebook run.

```python
flush_usage_to_dataset(
    "abc123-def4-5678-90ab-cdef12345678",  # dataset ID
    notebook_id="customer-churn-analysis",
    run_id=os.environ.get("DOMO_AUTOMATION_RUN_ID"),
)
```

#### Dataset schema

Create a Domo dataset with these columns before first flush:

| Column | Type | Source |
|---|---|---|
| `timestamp` | DATETIME | Set at flush time, UTC ISO-8601 |
| `model` | STRING | From `_config['llm_settings']['model']`, or override via `model=` arg |
| `input_tokens` | LONG | Chat input tokens (exact, from API) |
| `output_tokens` | LONG | Chat generation tokens (exact, from API) |
| `reasoning_tokens` | LONG | For thinking-class models; 0 on current models |
| `embedding_tokens_estimated` | LONG | **Estimated** from input chars/4; ±20% accurate |
| `total_tokens` | LONG | Sum of the four above |
| `chat_calls` | LONG | `prompt()` invocations since last reset |
| `embedding_calls` | LONG | `vector.embed()` invocations since last reset |
| `elapsed_seconds` | DOUBLE | Cumulative wall-clock across all calls |
| `notebook_id` | STRING | Caller-supplied identifier |
| `run_id` | STRING | Caller-supplied (e.g. Domo Automation run ID) |

To add custom columns, pass `extra={...}` to `flush_usage_to_dataset()` and add the matching columns to the dataset.

#### Append behavior

The flush helper does a **read-modify-write** to append (the SDK's data client lacks a true append primitive). Implications:

- Concurrent flushes can race and lose rows. Fine for once-per-notebook cost logging; *do not* call from inside a parallel-prompt loop.
- For new datasets, the first flush bootstraps the schema from the row's columns. Subsequent flushes match against existing columns.

If true append matters (high-frequency tracking, multi-notebook concurrency), the path is to add a Stream API wrapper to `data.py` — out of scope for v0.2.0 but easy to add later.

## What's tracked vs. not

**Tracked (exact, server-reported):**
- All `llm.prompt()` calls — input, output, and reasoning tokens.
- All `llm.parallel()` calls (delegate to `prompt()`).
- All `apps.create()` calls (uses `llm.prompt()` internally).

**Tracked (estimated, client-side from char count):**
- `vector.embed()` and `vector.embed_single()` — Domo's embedding endpoint returns no token count, so we estimate as `chars / 4`. Trend-accurate, ±20% on absolute values.

**NOT tracked:**
- `vector.query(input_text=...)` — when given text, this triggers an embedding call inside the Domo recall backend that doesn't surface to us. The recall API itself returns no usage info. Either pre-embed via `vector.embed()` then pass `embedding=`, or accept that recall queries are an untracked dimension.
- `vector.upsert()` — usually called with pre-computed embeddings, no AI cost.

## Limitations & caveats

1. **Embedding token counts are estimates.** Cohere's actual tokenizer would give better numbers; we keep it dependency-free with chars/4. Document the imprecision in cost reports.
2. **JSON-mode chat calls have inflated input cost.** Domo injects ~600+ system tokens to enforce structured output (see [ai-response-shape.md](ai-response-shape.md#cost-relevant-gotchas)). The accumulator captures this faithfully — it's not a bug, but expect higher input_tokens when `response_format=` is used.
3. **Counter is per-Python-process.** Notebooks running in separate kernels each have their own counter. Use `notebook_id` / `run_id` on flush to disambiguate.
4. **No per-model breakdown.** The current row schema records only the *configured* model. If a notebook switches models mid-run, the flush row reports the last-set model. To track per-model: call `flush_usage_to_dataset()` after each model switch and `reset_usage()` between them, or extend the schema.

## Future improvements

- True append via PyDomo Stream API (eliminates RMW race).
- Optional `auto_flush_to_dataset` config in `auth()` so flush happens implicitly at notebook end.
- Per-model breakdown (extra columns: `model_a_input_tokens`, etc.) once we hit the first multi-model notebook.
- Replace chars/4 embedding estimator with Cohere's actual tokenizer if `cohere` is added as an optional dep.
