# Phase 2 Evidence — Formatter layer

## New files
- `src/formatter.py` — format_greeting(name, style) wrapping greet()
- `tests/test_formatter.py` — 3 unit tests

## Modified files
(none — src/greeter.py and tests/test_greeter.py unchanged)

## Test run
```
$ python -m pytest tests/ -v
test_greet_normal PASSED
test_greet_empty PASSED
test_greet_none PASSED
test_upper PASSED
test_lower PASSED
test_title PASSED
6 passed in 0.14s
```

## Pre-existing tests
3 (from Phase 1, all still passing)
