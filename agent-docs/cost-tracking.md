# Cost tracking

Every notebook that calls `llm.prompt()`, `llm.parallel()`, or `vector.embed()` accumulates token usage **and USD cost** into a thread-safe global counter. The public API is two functions plus one helper, all under the `cost` namespace.

> See [ai-response-shape.md](ai-response-shape.md) for the underlying API response shape and why embedding tokens are estimated rather than measured. See [pricing.py](../domo_sdk/pricing.py) for the bundled per-model rate table.

## Quick start

```python
from domo_sdk import auth, llm, cost

auth(dev_token, client_id, client_secret)
cost.start()                                                    # reset counter at top

llm.prompt("Summarize this transcript: ...")
llm.parallel(items, lambda x: llm.prompt(f"Classify: {x}"))

cost.end(dataset_id="abc123-...", notebook_id="my-notebook")    # print + flush at bottom
# === my-notebook ===
#   47 chat calls, 0 embedding calls
#   12,044 input / 3,201 output tokens (15,245 total)
#   $0.10937 over 38.2s
#   flushed to dataset abc123-...
```

## API

### `cost.start()`

Reset the global counter. Call once at the top of a notebook run, after `auth()`.

### `cost.end(dataset_id=None, *, notebook_id=None, run_id=None, extra=None, quiet=False)`

Print a one-paragraph cost summary and (optionally) flush a row to a Domo dataset. Returns the row dict.

- **No `dataset_id`** → just prints + returns the row. No Domo write. Useful for local dev.
- **With `dataset_id`** → also appends a row to the dataset via read-modify-write.
- **`quiet=True`** → suppress the print. Returned dict is unchanged.
- **`extra={...}`** → optional dict merged into the row (target dataset must already have matching columns).

### `cost.phase(label)` — scoped sub-tracking

Context manager for measuring cost of a specific block inside a `cost.start()` / `cost.end()` pair. Tokens used inside still count toward the cumulative `cost.end()` total.

```python
cost.start()

with cost.phase("context cards") as p1:
    llm.parallel(items=opps, prompt_func=build_context, max_workers=10)
# [phase: context cards] 47 chat / 0 embed, $0.0936, 12.4s

with cost.phase("deal scoring") as p2:
    llm.parallel(items=deals, prompt_func=score, max_workers=10)
# [phase: deal scoring] 88 chat / 0 embed, $0.1742, 23.1s

cost.end(dataset_id="...", notebook_id="L2_deal_intelligence")
# (cumulative across both phases)
```

The `Phase` object exposes `input_tokens`, `output_tokens`, `reasoning_tokens`, `embedding_tokens_estimated`, `total_tokens`, `chat_calls`, `embedding_calls`, `cost_usd`, `elapsed_seconds`, and the `label` you passed in.

Phase blocks always print their delta on exit. To suppress, just don't pass anything — there's no `quiet` mode here (use a no-op block if you really need silence). Phases can be nested or sequential.

## Dataset schema

Pass a real `dataset_id` to `cost.end()` to append a row. The dataset can be empty on first call — the schema bootstraps from the row's columns. Subsequent calls match against existing columns. The columns:

| Column | Type | Source |
|---|---|---|
| `timestamp` | DATETIME | Set at flush time, UTC ISO-8601 |
| `model` | STRING | From `_config['llm_settings']['model']` at flush time |
| `input_tokens` | LONG | Chat input tokens (exact, from API) |
| `output_tokens` | LONG | Chat generation tokens (exact, from API) |
| `reasoning_tokens` | LONG | For thinking-class models; 0 on current models |
| `embedding_tokens_estimated` | LONG | **Estimated** from input chars/4; ±20% accurate |
| `total_tokens` | LONG | Sum of the four above |
| `chat_calls` | LONG | `prompt()` invocations since last `cost.start()` |
| `embedding_calls` | LONG | `vector.embed()` invocations since last `cost.start()` |
| `elapsed_seconds` | DOUBLE | Cumulative wall-clock across all calls |
| `cost_usd` | DOUBLE | USD cost computed from token counts × hardcoded rates in [pricing.py](../domo_sdk/pricing.py) |
| `notebook_id` | STRING | Caller-supplied identifier |
| `run_id` | STRING | Caller-supplied (e.g. Domo Automation run ID) |

To add custom columns, pass `extra={...}` to `cost.end()` and add the matching columns to the dataset.

### Append behavior

`cost.end(dataset_id=...)` does a **read-modify-write** append (the SDK's data client lacks a true append primitive). Implications:

- Concurrent flushes can race and lose rows. Fine for once-per-notebook cost logging; *do not* call from inside a parallel-prompt loop.
- For new datasets, the first flush bootstraps the schema from the row's columns. Subsequent flushes match against existing columns.

If true append matters (high-frequency tracking, multi-notebook concurrency), the path is to add a Stream API wrapper to `data.py` — listed in Future Improvements.

## How cost is calculated

The SDK only ever calls two models, so [pricing.py](../domo_sdk/pricing.py) hardcodes their rates as module-level constants. No lookup table, no model-name normalization, no per-call rate dispatch beyond `surface == "chat"` vs `surface == "embedding"`.

```python
CHAT_MODEL = "domo.domo_ai.domogpt-medium-v2.1"
CHAT_INPUT_USD_PER_M  = 3.90    # USD per 1M input tokens
CHAT_OUTPUT_USD_PER_M = 19.50   # USD per 1M output tokens (also reasoning tokens)

EMBEDDING_MODEL = "domo.domo_ai.domo-embed-text-multilingual-v1"
EMBEDDING_INPUT_USD_PER_M = 0.13
```

Per-call cost:

```python
# Chat
cost = (input_tokens  / 1e6) × 3.90
     + (output_tokens / 1e6) × 19.50
     + (reasoning_tokens / 1e6) × 19.50   # billed at output rate

# Embedding (input only — embedding models have no output)
cost = (estimated_tokens / 1e6) × 0.13
```

`pricing.chat_cost_usd(...)` and `pricing.embedding_cost_usd(...)` are the public helpers. `usage.record_call()` dispatches on `surface` to pick the right one.

### Why hardcoded, not a lookup table

The SDK's only consumers are notebooks that call `domogpt-medium-v2.1` for chat and the Cohere v1 embedding model — full stop. A 40-row table covering every model on the pricing page was speculative coverage that fights pricing-page drift more than it helps. Two named constants are easier to audit, easier to update, and impossible to accidentally use with the wrong model (see "Defensive warning" below).

Snapshot date for the rates is in [pricing.py](../domo_sdk/pricing.py)'s module docstring — refresh manually when Domo updates the page.

### Defensive warning if the model changes

If `_config['llm_settings']['model']` is changed (or `vector.embed(model=...)` is called with a different model), the API will return a different `modelId` — and the cost calc will be silently wrong because the rates above won't apply.

To make this fail loudly, both [llm._call_api](../domo_sdk/clients/llm.py) and [vector.embed](../domo_sdk/clients/vector.py) check the response's `modelId` against `pricing.CHAT_MODEL` / `pricing.EMBEDDING_MODEL` (with `startswith()` to ignore the `:provider` suffix the API appends). A mismatch emits a `UserWarning`:

```
Unexpected chat model 'domo.domo_ai.domogpt-large-v2.2:anthropic' — cost calc
assumes domo.domo_ai.domogpt-medium-v2.1. Update domo_sdk/pricing.py if this is intentional.
```

If you intentionally switch models, update the constants in `pricing.py` (and ideally only one model at a time, or the warning hides itself behind itself).

### Reasoning tokens

Domo doesn't separately price reasoning tokens. The SDK bills them at the **output rate**, matching Anthropic's billing model. On current v2.x models `reasoningTokens` is always null/zero so this is moot — relevant when reasoning models become available.

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

## Implementation notes (where the mechanics live)

For agents poking around the code:

- **`domo_sdk/cost.py`** — public façade. `start()`, `end(...)`, `phase(...)`, plus the `Phase` dataclass returned by the context manager. Thin wrapper.
- **`domo_sdk/usage.py`** — private accumulator. Module-level `_Counter` dataclass guarded by a `threading.Lock`. Exposes `record_call(...)` (called from `clients/llm.py` and `clients/vector.py`) and underscore-prefixed `_get_usage()` / `_reset_usage()` for `cost.py` to use. **Don't import the underscored names from outside `cost.py`** — that's the whole reason the surface was reduced.
- **`domo_sdk/pricing.py`** — hardcoded per-1M-token rates. `chat_cost_usd(...)` and `embedding_cost_usd(...)` are called from `record_call`.

The reason `cost.py` is a separate module from `usage.py` rather than just renaming the latter: `usage.py` is imported by `clients/llm.py` and `clients/vector.py` at SDK load time (for `record_call`), but `cost.py` imports `data` from the package root (for the dataset flush) — which doesn't exist until `__init__.py` finishes instantiating clients. Splitting keeps the import graph acyclic.

## Limitations & caveats

1. **Embedding token counts are estimates.** Cohere's actual tokenizer would give better numbers; we keep it dependency-free with chars/4. Document the imprecision in cost reports.
2. **JSON-mode chat calls have inflated input cost.** Domo injects ~600+ system tokens to enforce structured output (see [ai-response-shape.md](ai-response-shape.md#cost-relevant-gotchas)). The accumulator captures this faithfully — it's not a bug, but expect higher input_tokens when `response_format=` is used.
3. **Counter is per-Python-process.** Notebooks running in separate kernels each have their own counter. Use `notebook_id` / `run_id` on `cost.end()` to disambiguate.
4. **Single-model assumption.** Cost rates are hardcoded for `domo.domo_ai.domogpt-medium-v2.1` (chat) and `domo.domo_ai.domo-embed-text-multilingual-v1` (embedding). If a notebook switches models, a `UserWarning` fires from `llm._call_api` / `vector.embed`, and the cost number will be wrong until [pricing.py](../domo_sdk/pricing.py) is updated.

## Future improvements

- True append via PyDomo Stream API (eliminates RMW race in `cost.end(dataset_id=...)`).
- Optional `cost_dataset_id=` argument on `auth()` so `cost.end()` can flush implicitly without re-passing the ID. Or an `atexit` hook on `cost.start()` that auto-flushes if the user forgot to call `cost.end()`. Both have "magic" tradeoffs — leave them off until we feel real pain.
- Replace chars/4 embedding estimator with Cohere's actual tokenizer if `cohere` is added as an optional dep (would tighten the ±20% embedding cost estimate).
