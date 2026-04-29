"""
Domo AI pricing — only the models the SDK actually calls.

Source: https://www.domo.com/consumption-terms/ai-model-pricing (snapshot 2026-04-29)

Hardcoded for the two models the SDK invokes:
- Chat:      domo.domo_ai.domogpt-medium-v2.1            → $3.90 / $19.50 per 1M (input / output)
- Embedding: domo.domo_ai.domo-embed-text-multilingual-v1 → $0.13 per 1M (input only)

If a notebook ever switches to a different model, the warning in
llm._call_api / vector.embed will trip — fail loudly rather than silently
miscount. Update the rates below, NOT by reintroducing a lookup dict.
"""

CHAT_MODEL = "domo.domo_ai.domogpt-medium-v2.1"
CHAT_INPUT_USD_PER_M = 3.90
CHAT_OUTPUT_USD_PER_M = 19.50

EMBEDDING_MODEL = "domo.domo_ai.domo-embed-text-multilingual-v1"
EMBEDDING_INPUT_USD_PER_M = 0.13


def chat_cost_usd(input_tokens: int, output_tokens: int, reasoning_tokens: int = 0) -> float:
    """Cost in USD for a single chat call. Reasoning tokens billed at output rate."""
    return (
        (input_tokens / 1_000_000) * CHAT_INPUT_USD_PER_M
        + ((output_tokens + reasoning_tokens) / 1_000_000) * CHAT_OUTPUT_USD_PER_M
    )


def embedding_cost_usd(input_tokens: int) -> float:
    """Cost in USD for a single embedding call (input only)."""
    return (input_tokens / 1_000_000) * EMBEDDING_INPUT_USD_PER_M
