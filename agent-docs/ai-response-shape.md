# Domo AI `/api/ai/v1/messages/chat` response shape

> Captured 2026-04-29 by direct Product API probe from terminal (dev-token auth, instance `domo.domo.com`). Three calls — plain text, JSON-mode, and a different model — all returned the same envelope, so this shape is stable across models and response formats.

## Endpoint

`POST https://{instance}.domo.com/api/ai/v1/messages/chat`

Auth: `X-DOMO-Developer-Token: <token>` (Product API). The same SDK code path also works inside Jupyter Workspaces via `domojupyter.domo.Domo._post()`, which uses session auth.

## Response envelope

```json
{
  "content": [
    {
      "type": "TEXT",
      "text": "Hi there friend."
    }
  ],
  "modelId": "domo.domo_ai.domogpt-medium-v2.1:anthropic",
  "isCustomerModel": false,
  "sessionId": "7a5e6789-3a03-46d1-9f39-184d85117ea4",
  "requestId": "e6107dde-ec7a-4b7f-a79d-af72a4194fab",
  "stopReason": "END_TURN",
  "modelProviderUsage": {
    "inputTokens": 16,
    "outputTokens": 7,
    "totalTokens": 23,
    "reasoningTokens": null
  }
}
```

## Field reference

| Field | Type | Purpose |
|---|---|---|
| `content[0].text` | string | The model's response text. The only field the current SDK reads. |
| `modelId` | string | Resolved model. Note the `:anthropic` suffix — `domogpt-medium-v2.1` is currently backed by Anthropic. Provider can change without warning. |
| `isCustomerModel` | bool | True when the customer has a custom-trained model. |
| `sessionId` | string | UUID stable across requests using the same dev-token session. **Not** per-call — useful for grouping but not for unique identification. |
| `requestId` | string | UUID unique per call. **This is the right ID to log for traceability.** |
| `stopReason` | string | `END_TURN` on normal completion. Other values (e.g. `MAX_TOKENS`) signal truncation. |
| `modelProviderUsage.inputTokens` | int | Tokens consumed by the prompt (system + conversation + user message). |
| `modelProviderUsage.outputTokens` | int | Tokens generated in the response. |
| `modelProviderUsage.totalTokens` | int | `inputTokens + outputTokens`. Provided for convenience. |
| `modelProviderUsage.reasoningTokens` | int \| null | Reasoning/thinking tokens for models that expose them. Currently null on all v2.1 calls. |

## Cost-relevant gotchas

1. **JSON mode is expensive on the input side.** A trivial prompt (`Return JSON: {"city":"Paris"}`) with `responseFormat` set burned **662 input tokens** vs. **16 input tokens** for the same-length plain prompt. Domo injects a substantial system prompt to enforce structured output. Worth flagging when notebooks use `response_format` heavily — the cost model is very different from plain calls.

2. **`reasoningTokens` is presently null** on v2.1 models. Plan for it being populated on future reasoning-class models — tracking code should sum it into total cost when non-null, since reasoning tokens are typically billed at output rates.

3. **`sessionId` reuse**. Three back-to-back calls from the same dev token returned the same `sessionId`. If you log `sessionId` thinking it identifies a unique call, you'll be wrong. Use `requestId` for per-call uniqueness.

4. **Provider suffix in `modelId`.** The actual provider (`:anthropic`) is appended at request time. If we ever build a per-provider cost lookup, parse the segment after `:`.

## Embedding endpoint: `/api/ai/v1/embedding/text`

Probed alongside chat for completeness, since `vector.embed()` calls it directly. **Crucially: embedding responses do not return token usage.**

```json
{
  "embeddings": [[/* 1024 floats */], [/* 1024 floats */]],
  "modelId": "domo.domo_ai.domo-embed-text-multilingual-v1:cohere",
  "isCustomerModel": false,
  "modelProviderUsage": null
}
```

The `modelProviderUsage` field is present but explicitly `null` — Domo isn't surfacing the embedding model's token count today. Implication: **embedding cost cannot be measured server-side; it must be estimated client-side** (e.g. character or word count × a per-model rate). This is a known limitation; document in cost-tracking docs and revisit if Domo starts populating the field.

Note that `vector.query(input_text=...)` triggers an embedding call inside the `/api/recall/v1/...` backend — also invisible to us. Recommend tracking only embeddings made via `vector.embed()` (visible) and noting recall queries as an untracked dimension.

## Implication for tracking code

The SDK's `llm._call_api()` currently reads only `response["content"][0]["text"]`. To track usage:

```python
usage = response.get("modelProviderUsage", {}) or {}
input_tokens = usage.get("inputTokens", 0) or 0
output_tokens = usage.get("outputTokens", 0) or 0
reasoning_tokens = usage.get("reasoningTokens") or 0
# Accumulate input_tokens + output_tokens + reasoning_tokens
# Also capture: response["modelId"], response["requestId"], response["stopReason"]
```

Defensive `.get(...) or 0` matters because `reasoningTokens` is explicitly `null` (not absent) in current responses — `.get("reasoningTokens", 0)` would return `None`, not `0`.
