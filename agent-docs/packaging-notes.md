# Packaging notes

## Status

`pyproject.toml` was restored 2026-04-29. Build and install verified end-to-end:

```bash
python3.12 -m venv /tmp/sdktest
/tmp/sdktest/bin/pip install --no-deps /path/to/domo-python-sdk
# → Successfully installed domo-sdk-0.2.0
```

## Dep audit

Deps were derived from a literal grep of all `import` / `from` statements under `domo_sdk/`. The deleted (commit 2906a64) pyproject had `IPython` listed but `IPython` is NOT imported anywhere in the codebase — dropped.

Currently declared:

| Package | Where used | Notes |
|---|---|---|
| `domojupyter` | `core.py` | **Domo-only**, not on public PyPI |
| `pydomo` | `core.py` | OAuth client; on PyPI |
| `requests` | `web.py` | Standard |
| `urllib3` | `web.py` | Standard (transitive of requests but explicitly imported) |
| `pandas` | `data.py`, etc. | 2.x range |
| `numpy` | `vector.py` | Used by sklearn integration |
| `scikit-learn` | `vector.py` | `cosine_similarity` only — heavy dep for one function (potential simplification target) |
| `beautifulsoup4` | `web.py` | HTML scraping |

## Known limitation: `domojupyter` is Domo-runtime-only

`from domojupyter.domo import Domo` at the top of `core.py` means **`import domo_sdk` will fail on any machine without the Domo Jupyter Workspaces runtime.** This is acceptable today — the SDK is designed for notebooks running on Domo Automation — but has consequences:

- Local dev/testing impossible without mocking `domojupyter`
- CI cannot import-test the package
- Any future package-level static analysis (mypy in CI) requires either a stub or a lazy-import refactor

**Future improvement (not in scope for the 0.2.0 packaging restore):** lazy-import `domojupyter` inside `auth()` so the package itself can import without the Domo runtime. This would unlock local unit tests for non-Domo-dependent modules (`templates.py`, similarity math in `vector.py`).

## Why `scikit-learn` is overkill but kept

`vector.py` imports a single function: `from sklearn.metrics.pairwise import cosine_similarity`. The whole sklearn dependency (~120MB with numpy/scipy stack) for one cosine math function is a candidate for replacement with a 3-line numpy implementation. Keeping the dep for now since refactoring it is out of scope; flag it for a future cleanup.
