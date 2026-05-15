# code-reviewer checkpoint — Phase 2 — format_version: 1

## Skip list (do NOT re-read unless in future evidence as modified)
- `src/greeter.py` — 4-line greet(name) function; handles None/empty via `if not name:`; type annotation is `str` but None is accepted (known gap, carried forward)
- `tests/test_greeter.py` — 3 unit tests (test_greet_normal, test_greet_empty, test_greet_none); all assert on return value; no fragility
- `src/formatter.py` — 9-line format_greeting(name, style="title"); delegates to greet(); three if-branches for upper/lower/title; no redundant None guard; unknown style silently falls through to title
- `tests/test_formatter.py` — 3 unit tests (test_upper, test_lower, test_title); all assert on exact return string; no fragility

## Changed this phase
- `src/formatter.py` (new)
- `tests/test_formatter.py` (new)

## Patterns established
- Python with type annotations (stdlib only, no third-party imports)
- pytest for unit testing (no fixtures; direct function calls; assertions on return value)
- Import path: `from src.* import *` — tests run from project root
- Layered delegation: formatter wraps greeter without duplicating its guards

## Running concerns
- `name: str` annotation gap (from Phase 1) now propagates through formatter.py as well. If a future phase adds callers, None can silently flow through both layers. Annotation fix (str → Optional[str]) remains low-urgency but should be done before any public API exposure.
- Unknown `style` values fall through silently to `title` in formatter.py. Not a bug per current spec but worth noting if style enum grows.

## Phase 2 verdict
APPROVE — no critical issues, tests meaningful and complete, no pattern violations, no regressions.
