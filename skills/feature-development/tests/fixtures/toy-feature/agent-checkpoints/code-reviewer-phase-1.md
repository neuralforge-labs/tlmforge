# code-reviewer checkpoint — Phase 1 — format_version: 1

## Skip list (do NOT re-read unless in future evidence as modified)
- `src/greeter.py` — 4-line greet(name) function; handles None/empty via `if not name:`; type annotation is `str` but None is accepted (known gap)
- `tests/test_greeter.py` — 3 unit tests (test_greet_normal, test_greet_empty, test_greet_none); all assert on return value; no fragility

## Changed this phase
- `src/greeter.py` (new)
- `tests/test_greeter.py` (new)

## Patterns established
- Python with type annotations (stdlib only, no third-party imports seen)
- pytest for unit testing (no fixtures used yet; direct function calls)
- Import path: `from src.greeter import greet` — implies tests run from project root with `src/` as a package or on PYTHONPATH

## Running concerns
- `greet(name: str)` annotation does not reflect that None is a valid/tested input. If Phase 2 calls `greet()` and relies on the type signature, it may pass None without knowing it is supported, or may add redundant guards. Flag if formatter.py adds None-handling that duplicates greeter.py's existing guard.

## Next phase scope (from spec)
- Files expected: `src/formatter.py`, `tests/test_formatter.py`
