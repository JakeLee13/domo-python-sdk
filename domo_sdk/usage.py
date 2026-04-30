"""
Internal token-usage accumulator for the Domo SDK.

This module is the low-level mechanics — the thread-safe counter that
`clients/llm.py` and `clients/vector.py` write to via `record_call()`.

Notebooks should use the `cost` module (cost.start / cost.end / cost.phase)
instead of touching anything here directly. The leading underscores on
`_reset_usage`, `_get_usage`, and `_Counter` flag the private boundary.

Embedding cost note:
    The Domo embedding endpoint does not return token counts (see
    agent-docs/ai-response-shape.md). Embedding usage is *estimated*
    client-side from input character count using a coarse heuristic
    (chars / 4 ≈ tokens). Treat embedding token totals as ±20% accurate;
    chat token totals come straight from the API and are exact.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from . import pricing


@dataclass
class _Counter:
    """Mutable accumulator for one usage 'session' (global)."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    embedding_tokens_estimated: int = 0
    chat_calls: int = 0
    embedding_calls: int = 0
    elapsed_seconds: float = 0.0
    cost_usd: float = 0.0
    started_at: float = field(default_factory=time.time)

    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.reasoning_tokens
            + self.embedding_tokens_estimated
        )


_lock = threading.Lock()
_global = _Counter()


def record_call(
    *,
    surface: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
    embedding_tokens_estimated: int = 0,
    elapsed_seconds: float = 0.0,
) -> None:
    """
    Record a single API call's usage. Thread-safe.

    Called from `llm._call_api()` and `vector.embed()`. Notebooks should
    not call this directly — use the `cost` module instead.

    Cost is computed from the surface (chat vs embedding) using the hardcoded
    rates in `pricing.py`. Callers must guarantee the model matches
    `pricing.CHAT_MODEL` / `pricing.EMBEDDING_MODEL`; the warning hooks in
    `llm._call_api` and `vector.embed` enforce that loudly.

    Args:
        surface: 'chat' or 'embedding' — which API surface produced this call
        input_tokens: Prompt tokens (chat) or 0 (embedding — see embedding_tokens_estimated)
        output_tokens: Generation tokens (chat) or 0 (embedding has no output)
        reasoning_tokens: Reasoning tokens for thinking models, or 0
        embedding_tokens_estimated: Estimated tokens for embedding calls.
        elapsed_seconds: Wall-clock time for this call
    """
    if surface == "chat":
        call_cost = pricing.chat_cost_usd(input_tokens, output_tokens, reasoning_tokens)
    elif surface == "embedding":
        call_cost = pricing.embedding_cost_usd(embedding_tokens_estimated)
    else:
        call_cost = 0.0

    with _lock:
        if surface == "chat":
            _global.chat_calls += 1
        elif surface == "embedding":
            _global.embedding_calls += 1
        # Unknown surfaces are still recorded under tokens but not counted as calls.

        _global.input_tokens += input_tokens
        _global.output_tokens += output_tokens
        _global.reasoning_tokens += reasoning_tokens
        _global.embedding_tokens_estimated += embedding_tokens_estimated
        _global.elapsed_seconds += elapsed_seconds
        _global.cost_usd += call_cost


def _get_usage() -> dict[str, Any]:
    """Snapshot of accumulated usage. Used by cost.end() and cost.phase()."""
    with _lock:
        return {
            "input_tokens": _global.input_tokens,
            "output_tokens": _global.output_tokens,
            "reasoning_tokens": _global.reasoning_tokens,
            "embedding_tokens_estimated": _global.embedding_tokens_estimated,
            "total_tokens": _global.total_tokens(),
            "chat_calls": _global.chat_calls,
            "embedding_calls": _global.embedding_calls,
            "elapsed_seconds": _global.elapsed_seconds,
            "cost_usd": _global.cost_usd,
            "started_at": _global.started_at,
        }


def _reset_usage() -> None:
    """Reset the global accumulator. Used by cost.start()."""
    global _global
    with _lock:
        _global = _Counter()
