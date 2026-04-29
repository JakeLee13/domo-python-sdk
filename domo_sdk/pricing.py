"""
Domo AI model pricing — USD per 1M tokens.

Bundled as a Python dict so cost calc works offline and is deterministic.
Refresh manually when Domo updates pricing (see `scripts/refresh-pricing.py`).

Source: https://www.domo.com/consumption-terms/ai-model-pricing
Pricing snapshot: 2026-04-29 (covers Oct 2025 — Mar 2026 effective dates)

Naming gotcha — three different conventions for the same model:

  API request input:    "domo.domo_ai.domogpt-medium-v2.1"
                        (dots, used in payload['model'] and config['llm_settings']['model'])

  API response modelId: "domo.domo_ai.domogpt-medium-v2.1:anthropic"
                        (above + ":provider" suffix)

  Pricing-page name:    "ai-pro-model-processing-llm-domogpt-anthropic-medium-v2_1-input"
                        (underscores, prefixed with billing namespace)

This module keys on the API request format (canonical for tracking purposes).
`normalize_model_id()` strips the response suffix to get back to that format.
"""

from __future__ import annotations

# Per-1M-token rates in USD. None means input-only model (no output cost).
# All Anthropic-backed domogpt variants share rates by tier; explicit duplicates
# kept for direct lookup rather than family-prefix matching (cheaper and clearer).
PRICING_USD_PER_M_TOKENS: dict[str, dict[str, float | None]] = {
    # Anthropic-backed domogpt — small tier
    "domo.domo_ai.domogpt-small-v1": {"input": 0.325, "output": 1.625},
    "domo.domo_ai.domogpt-small-v1_1": {"input": 1.04, "output": 5.20},
    "domo.domo_ai.domogpt-small-v2.1": {"input": 1.30, "output": 6.50},

    # Anthropic-backed domogpt — medium tier
    # NOTE: pricing page lists v1, v1_1, v1_2 (older) at $3.90/$19.50 — same
    # as the v2 line. API serves v2.1 and v2.2; medium-v1.x identifiers may
    # 404 on the chat endpoint (instance-dependent). Listing all for completeness.
    "domo.domo_ai.domogpt-medium-v1": {"input": 3.90, "output": 19.50},
    "domo.domo_ai.domogpt-medium-v1.1": {"input": 3.90, "output": 19.50},
    "domo.domo_ai.domogpt-medium-v1.2": {"input": 3.90, "output": 19.50},
    "domo.domo_ai.domogpt-medium-v2": {"input": 3.90, "output": 19.50},
    "domo.domo_ai.domogpt-medium-v2.1": {"input": 3.90, "output": 19.50},
    "domo.domo_ai.domogpt-medium-v2.2": {"input": 3.90, "output": 19.50},

    # Anthropic-backed domogpt — large tier
    "domo.domo_ai.domogpt-large-v2.2": {"input": 6.50, "output": 32.50},

    # Embeddings (input only — no output tokens). Note: API returns
    # "domo.domo_ai.domo-embed-text-multilingual-v1:cohere" but we key on the
    # stripped form (normalize_model_id removes the ':provider' suffix).
    "domo.domo_ai.domo-embed-text-multilingual-v1": {"input": 0.13, "output": None},
    "domo.openai.text-embedding-ada-002": {"input": 0.065, "output": None},

    # OpenAI direct
    "domo.openai.gpt-4o": {"input": 3.25, "output": 13.00},
    "domo.openai.gpt-4o-mini": {"input": 0.195, "output": 0.78},
    "domo.openai.gpt-4": {"input": 39.00, "output": 78.00},
    "domo.openai.gpt-5-mini": {"input": 0.325, "output": 2.60},
    "domo.openai.gpt-5": {"input": 1.625, "output": 13.00},
    "domo.openai.gpt-5.1": {"input": 1.625, "output": 13.00},
    "domo.openai.gpt-5.2": {"input": 2.275, "output": 18.20},

    # Anthropic direct (added Mar 2026)
    "domo.anthropic.claude-haiku-4.5": {"input": 1.30, "output": 6.50},
    "domo.anthropic.claude-sonnet-4.6": {"input": 3.90, "output": 19.50},
    "domo.anthropic.claude-opus-4.6": {"input": 6.50, "output": 32.50},

    # Databricks-routed Claude (added Feb 2026)
    "domo.databricks.claude-sonnet-3.7": {"input": 3.90, "output": 19.50},
    "domo.databricks.claude-sonnet-4": {"input": 3.90, "output": 19.50},
    "domo.databricks.claude-sonnet-4.5": {"input": 3.90, "output": 19.50},
    "domo.databricks.claude-haiku-4.5": {"input": 1.30, "output": 6.50},
    "domo.databricks.llama-maverick-4": {"input": 0.65, "output": 1.95},

    # Google Gemini
    "domo.google.gemini-flash-2.5": {"input": 0.39, "output": 3.25},
    "domo.google.gemini-pro-2.5": {"input": 1.625, "output": 13.00},
    "domo.google.gemini-flash-3": {"input": 0.65, "output": 3.90},
    "domo.google.gemini-pro-3": {"input": 2.60, "output": 15.60},

    # Snowflake Llama
    "domo.snowflake.llama3.1-405b": {"input": 11.70, "output": 11.70},
    "domo.snowflake.llama3.1-70b": {"input": 4.719, "output": 4.719},
    "domo.snowflake.llama3.1-8b": {"input": 0.741, "output": 0.741},
    "domo.snowflake.claude-sonnet-4": {"input": 3.90, "output": 19.50},
}

# Reasoning tokens are billed at the output rate when present.
# (Domo doesn't separately price reasoning tokens; this matches Anthropic's billing model.)


def normalize_model_id(model_id: str | None) -> str | None:
    """
    Strip the ':provider' suffix that Domo AI appends to response modelIds.

    The API returns "domo.domo_ai.domogpt-medium-v2.1:anthropic" but accepts
    "domo.domo_ai.domogpt-medium-v2.1" in requests. The pricing table is keyed
    on the request form, so normalize here.
    """
    if not model_id:
        return None
    return model_id.split(":")[0]


def calculate_cost_usd(
    model_id: str | None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
) -> float | None:
    """
    Compute cost in USD for a single API call.

    Args:
        model_id: The model identifier (with or without ':provider' suffix).
        input_tokens: Prompt tokens.
        output_tokens: Generation tokens.
        reasoning_tokens: Reasoning tokens (billed at output rate).

    Returns:
        Cost in USD, or None if the model isn't in the pricing table.
        Returning None (not 0.0) makes "unknown model" visible in aggregates
        rather than silently treated as free.
    """
    key = normalize_model_id(model_id)
    if key is None:
        return None

    rates = PRICING_USD_PER_M_TOKENS.get(key)
    if rates is None:
        return None

    input_rate = rates.get("input")
    output_rate = rates.get("output")

    cost = 0.0
    if input_rate is not None:
        cost += (input_tokens / 1_000_000) * input_rate
    if output_rate is not None:
        cost += ((output_tokens + reasoning_tokens) / 1_000_000) * output_rate

    return cost


def is_known_model(model_id: str | None) -> bool:
    """True if the model has a pricing entry. Useful for cost-coverage warnings."""
    return normalize_model_id(model_id) in PRICING_USD_PER_M_TOKENS
