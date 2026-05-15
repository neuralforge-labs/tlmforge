# toy-feature — Master Plan

## Context
Add a simple greeting module with two phases.

## Phase 1 — Core greeting logic
**Goal:** Add a `greet(name)` function and its tests.
**Files:** `src/greeter.py` (new), `tests/test_greeter.py` (new)
**Tests:** unit test for greet() with normal name, empty name, None input
**Rollback:** delete both files

## Phase 2 — Formatter layer
**Goal:** Add a `format_greeting(greeting, style)` function that wraps greet().
**Files:** `src/formatter.py` (new), `tests/test_formatter.py` (new)
**Tests:** unit test for format_greeting() with style=upper, lower, title
**Rollback:** delete both files
