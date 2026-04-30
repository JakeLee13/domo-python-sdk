"""
Cost tracking for Domo SDK notebooks.

Three functions:

    cost.start()        # at top of notebook, after auth()
    cost.end(...)       # at bottom — prints summary, optionally flushes to a dataset
    cost.phase("label") # context manager for scoped sub-tracking

Every chat (`llm.prompt`, `llm.parallel`) and embedding (`vector.embed`) call
adds tokens + USD cost to a thread-safe global counter. `cost.end()` reads
that counter, prints a summary, and (when given a dataset_id) appends a row
to a Domo dataset for cross-run analysis.

Example:
    from domo_sdk import auth, llm, cost

    auth(...)
    cost.start()

    llm.prompt("Summarize this transcript: ...")
    llm.parallel(items, lambda x: llm.prompt(f"Classify: {x}"))

    cost.end(dataset_id="DATASET_ID", notebook_id="L1_call_analyses")
    # === L1_call_analyses ===
    #   47 chat calls, 0 embedding calls
    #   12,044 input / 3,201 output tokens (15,245 total)
    #   $0.10937 over 38.2s
"""

from __future__ import annotations

import datetime
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from . import usage


@dataclass
class Phase:
    """
    Result of a `cost.phase()` block — the delta of usage during the block.

    Populated on context-manager exit. Tokens used inside the block are also
    counted in the global accumulator (so `cost.end()` after a phase still
    reflects them).
    """

    label: str
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    embedding_tokens_estimated: int = 0
    total_tokens: int = 0
    chat_calls: int = 0
    embedding_calls: int = 0
    elapsed_seconds: float = 0.0
    cost_usd: float = 0.0


def start() -> None:
    """Reset the global counter. Call once at the top of a notebook run."""
    usage._reset_usage()


def end(
    dataset_id: str | None = None,
    *,
    notebook_id: str | None = None,
    run_id: str | None = None,
    extra: dict[str, Any] | None = None,
    quiet: bool = False,
) -> dict[str, Any]:
    """
    Print a cost summary and (optionally) flush a row to a Domo dataset.

    With no `dataset_id`: just prints the summary and returns the row dict —
    no Domo write. Useful during local dev or when you only want to see cost
    in the notebook output.

    With `dataset_id`: also appends a row to the dataset via read-modify-write
    (data.get → concat → data.replace). For new/empty datasets the schema
    bootstraps from the row's columns. Concurrent flushes can race and lose
    rows — this is acceptable for once-per-notebook cost logging; do not call
    inside a parallel loop.

    Args:
        dataset_id: Domo dataset ID to append to. Omit to skip the write.
        notebook_id: Caller-supplied identifier (e.g. "L1_call_analyses").
        run_id: Caller-supplied run identifier (e.g. Domo Automation run ID).
        extra: Optional dict merged into the row. Columns must already exist
            in the target dataset.
        quiet: Suppress the printed summary. Returned dict is unchanged.

    Returns:
        The row dict that was (or would have been) written.
    """
    snapshot = usage._get_usage()

    # Lazy imports to dodge the circular: usage.py is imported by clients/llm.py,
    # and __init__.py instantiates clients before this module loads at runtime.
    from . import data as data_client
    from .core import _config

    row = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model": _config.get("llm_settings", {}).get("model", ""),
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

    if not quiet:
        header = f"=== {notebook_id} ===" if notebook_id else "=== run summary ==="
        print(header)
        print(f"  {row['chat_calls']} chat calls, {row['embedding_calls']} embedding calls")
        print(
            f"  {row['input_tokens']:,} input / {row['output_tokens']:,} output tokens "
            f"({row['total_tokens']:,} total)"
        )
        print(f"  ${row['cost_usd']:.5f} over {row['elapsed_seconds']:.1f}s")

    if dataset_id:
        import pandas as pd

        new_df = pd.DataFrame([row])
        try:
            existing = data_client.get(dataset_id)
            combined = pd.concat([existing, new_df], ignore_index=True)
        except Exception:
            combined = new_df

        data_client.replace(dataset_id, combined)
        if not quiet:
            print(f"  flushed to dataset {dataset_id}")

    return row


@contextmanager
def phase(label: str) -> Iterator[Phase]:
    """
    Scoped sub-tracking inside a cost.start() / cost.end() pair.

    Useful when a notebook does multiple LLM-heavy passes and you want to see
    each one's cost separately. Tokens used inside the block also count toward
    the cumulative `cost.end()` total.

    Example:
        cost.start()
        with cost.phase("context cards") as p1:
            llm.parallel(items=opps, prompt_func=build_context, max_workers=10)
        with cost.phase("deal scoring") as p2:
            llm.parallel(items=deals, prompt_func=score, max_workers=10)
        cost.end()  # prints cumulative across both phases

    The Phase object is printed on exit:
        [phase: context cards] 47 calls, $0.0936, 12.4s
    """
    snapshot_in = usage._get_usage()
    start_time = time.time()
    p = Phase(label=label)
    try:
        yield p
    finally:
        snapshot_out = usage._get_usage()
        p.input_tokens = snapshot_out["input_tokens"] - snapshot_in["input_tokens"]
        p.output_tokens = snapshot_out["output_tokens"] - snapshot_in["output_tokens"]
        p.reasoning_tokens = (
            snapshot_out["reasoning_tokens"] - snapshot_in["reasoning_tokens"]
        )
        p.embedding_tokens_estimated = (
            snapshot_out["embedding_tokens_estimated"]
            - snapshot_in["embedding_tokens_estimated"]
        )
        p.total_tokens = snapshot_out["total_tokens"] - snapshot_in["total_tokens"]
        p.chat_calls = snapshot_out["chat_calls"] - snapshot_in["chat_calls"]
        p.embedding_calls = (
            snapshot_out["embedding_calls"] - snapshot_in["embedding_calls"]
        )
        p.cost_usd = snapshot_out["cost_usd"] - snapshot_in["cost_usd"]
        p.elapsed_seconds = time.time() - start_time
        print(
            f"[phase: {label}] {p.chat_calls} chat / {p.embedding_calls} embed, "
            f"${p.cost_usd:.5f}, {p.elapsed_seconds:.1f}s"
        )
