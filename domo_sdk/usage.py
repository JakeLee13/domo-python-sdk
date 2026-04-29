"""
Token usage tracking for the Domo SDK.

Every LLM and embedding call routes through `record_call(...)`, which
accumulates totals into a thread-safe module-level counter. Notebooks read
the accumulated total via `get_usage()`, scope a block with
`with track() as t:`, or flush a row to a Domo dataset with
`flush_to_dataset(...)`.

Why a single shared counter (and not per-client counters):
    Cost reporting is an aggregate question — "what did this notebook run
    cost?" — that mixes chat tokens and embedding tokens. Keeping one
    accumulator means callers don't have to remember to query both.
    The `surface` field on each row distinguishes them when needed.

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
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from . import pricing


@dataclass
class _Counter:
    """Mutable accumulator for one usage 'session' (global or scoped)."""

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
    not call this directly — use `get_usage()` to read instead.

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


def get_usage() -> dict[str, Any]:
    """
    Return a snapshot of accumulated usage since the last `reset_usage()`.

    Returns:
        dict with input_tokens, output_tokens, reasoning_tokens,
        embedding_tokens_estimated, total_tokens, chat_calls, embedding_calls,
        elapsed_seconds, started_at.
    """
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


def reset_usage() -> None:
    """Reset the global accumulator. Call at the start of a notebook run."""
    global _global
    with _lock:
        _global = _Counter()


class TrackingContext:
    """Snapshot/diff against the global counter for scoped tracking."""

    def __init__(self) -> None:
        self._snapshot: dict[str, Any] = {}
        self._start: float = 0.0
        # Populated on __exit__:
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.reasoning_tokens: int = 0
        self.embedding_tokens_estimated: int = 0
        self.total_tokens: int = 0
        self.chat_calls: int = 0
        self.embedding_calls: int = 0
        self.elapsed_seconds: float = 0.0
        self.cost_usd: float = 0.0

    def __enter__(self) -> "TrackingContext":
        self._snapshot = get_usage()
        self._start = time.time()
        return self

    def __exit__(self, *_exc: Any) -> None:
        end = get_usage()
        self.input_tokens = end["input_tokens"] - self._snapshot["input_tokens"]
        self.output_tokens = end["output_tokens"] - self._snapshot["output_tokens"]
        self.reasoning_tokens = (
            end["reasoning_tokens"] - self._snapshot["reasoning_tokens"]
        )
        self.embedding_tokens_estimated = (
            end["embedding_tokens_estimated"]
            - self._snapshot["embedding_tokens_estimated"]
        )
        self.total_tokens = end["total_tokens"] - self._snapshot["total_tokens"]
        self.chat_calls = end["chat_calls"] - self._snapshot["chat_calls"]
        self.embedding_calls = (
            end["embedding_calls"] - self._snapshot["embedding_calls"]
        )
        self.cost_usd = end["cost_usd"] - self._snapshot["cost_usd"]
        self.elapsed_seconds = time.time() - self._start


@contextmanager
def track() -> Iterator[TrackingContext]:
    """
    Context manager for scoped usage tracking.

    Tokens used inside the block are still counted in the global accumulator
    (so `get_usage()` after the block reflects them). The context object
    additionally exposes the *delta* — only what happened inside the block.

    Example:
        with track() as t:
            llm.prompt("Hello")
            llm.prompt("World")
        print(t.chat_calls, t.total_tokens)  # 2, ~30
    """
    ctx = TrackingContext()
    with ctx:
        yield ctx


def flush_to_dataset(
    dataset_id: str,
    *,
    notebook_id: str | None = None,
    run_id: str | None = None,
    model: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Append a row of accumulated usage to a Domo dataset.

    The row is appended via read-modify-write (data.get → concat → data.replace),
    because the SDK's data client does not currently expose a true append
    primitive. This is fine for low-frequency cost logging (one row per
    notebook run); concurrent flushes can race and lose rows.

    Args:
        dataset_id: Domo dataset ID to write to. Schema must match the
            columns documented in agent-docs/cost-tracking.md.
        notebook_id: Optional notebook identifier (caller-supplied).
        run_id: Optional run identifier (e.g. Domo Automation run ID).
        model: Optional model name. Defaults to the configured chat model.
        extra: Optional dict of extra fields to merge into the row. Must
            match columns that already exist in the target dataset.

    Returns:
        The flushed row as a dict.
    """
    import datetime

    import pandas as pd

    # Lazy import to avoid circular dependency at module load (usage.py is
    # imported by clients/llm.py, and __init__.py instantiates clients).
    from . import data as data_client
    from .core import _config

    snapshot = get_usage()
    row = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model": model or _config.get("llm_settings", {}).get("model", ""),
        "input_tokens": snapshot["input_tokens"],
        "output_tokens": snapshot["output_tokens"],
        "reasoning_tokens": snapshot["reasoning_tokens"],
        "embedding_tokens_estimated": snapshot["embedding_tokens_estimated"],
        "total_tokens": snapshot["total_tokens"],
        "chat_calls": snapshot["chat_calls"],
        "embedding_calls": snapshot["embedding_calls"],
        "elapsed_seconds": snapshot["elapsed_seconds"],
        "cost_usd": snapshot["cost_usd"],
        "notebook_id": notebook_id or "",
        "run_id": run_id or "",
    }
    if extra:
        row.update(extra)

    # Read-modify-write append. Domo's data client doesn't expose a true
    # append primitive, so concurrent flushes can race. Acceptable for
    # once-per-notebook cost logging.
    new_df = pd.DataFrame([row])
    try:
        existing = data_client.get(dataset_id)
        combined = pd.concat([existing, new_df], ignore_index=True)
    except Exception:
        combined = new_df

    data_client.replace(dataset_id, combined)
    return row
