#!/usr/bin/env python3
"""Test impact graph analyzer (TDAD).

Given a Python source root, a tests root, and a list of changed files, return the set of
test files that import the changed files (directly or transitively).

Usage:
    analyzer.py --src-root <path> --tests-root <path> --changed-files <files...>
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import sys


def collect_python_files(root: pathlib.Path) -> list[pathlib.Path]:
    """All .py files under root (recursive)."""
    if not root.exists():
        return []
    return [p for p in root.rglob("*.py") if "__pycache__" not in str(p)]


def file_to_module(path: pathlib.Path, src_root: pathlib.Path) -> str | None:
    """Convert a file path to a dotted module name, given the src root."""
    try:
        rel = path.relative_to(src_root)
    except ValueError:
        return None
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts) if parts else None


def parse_imports(path: pathlib.Path) -> set[str]:
    """Return the set of dotted module names this file imports."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
                # Also include sub-imports as fully-qualified
                for alias in node.names:
                    imports.add(f"{node.module}.{alias.name}")
    return imports


def build_module_to_file_map(src_files: list[pathlib.Path], src_root: pathlib.Path) -> dict:
    """module_name → file path, for all files under src_root."""
    out = {}
    for f in src_files:
        m = file_to_module(f, src_root)
        if m:
            out[m] = f
    return out


def build_reverse_dep_graph(
    all_files: list[pathlib.Path],
    module_to_file: dict,
    src_root: pathlib.Path,
) -> dict:
    """For each module, list of files that directly import it."""
    reverse: dict = {m: set() for m in module_to_file}
    for f in all_files:
        imports = parse_imports(f)
        for imp in imports:
            # Check if imp is in our project (matches a module we know about)
            # OR is a parent of one (e.g. import "myapp.auth" matches "myapp.auth.login")
            for known_mod in module_to_file:
                if imp == known_mod or known_mod.startswith(imp + "."):
                    reverse[known_mod].add(f)
    return reverse


def transitive_closure(
    seed_files: set[pathlib.Path],
    reverse_graph: dict,
    module_to_file: dict,
    src_root: pathlib.Path,
) -> set[pathlib.Path]:
    """Given seed files, return all files that transitively depend on them."""
    impacted: set[pathlib.Path] = set(seed_files)
    queue = list(seed_files)
    while queue:
        current = queue.pop()
        current_module = file_to_module(current, src_root)
        if current_module is None:
            continue
        importers = reverse_graph.get(current_module, set())
        for importer in importers:
            if importer not in impacted:
                impacted.add(importer)
                queue.append(importer)
    return impacted


def filter_to_test_files(files: set[pathlib.Path], tests_root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(
        f for f in files
        if str(f).startswith(str(tests_root)) or "test_" in f.name or f.name.endswith("_test.py")
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute test impact graph for a Python diff.")
    ap.add_argument("--src-root", type=pathlib.Path, required=True)
    ap.add_argument("--tests-root", type=pathlib.Path, required=True)
    ap.add_argument("--changed-files", nargs="+", required=True)
    ap.add_argument("--full-suite-on-fixtures", action="store_true", default=True,
                    help="If a fixture file changed, return [] (signaling 'run full suite').")
    args = ap.parse_args()

    src_root = args.src_root.resolve()
    tests_root = args.tests_root.resolve()

    changed_files = []
    for f in args.changed_files:
        p = pathlib.Path(f).resolve()
        if not p.exists():
            print(f"# WARN: changed file not found: {f}", file=sys.stderr)
            continue
        changed_files.append(p)

    if not changed_files:
        print("# no changed files resolved; nothing to do", file=sys.stderr)
        return 0

    # Conservative: any conftest.py or fixtures dir change → recommend full suite
    for f in changed_files:
        if f.name == "conftest.py" or "fixtures" in f.parts:
            print("# conftest.py or fixtures changed — recommend running full suite", file=sys.stderr)
            return 0

    src_files = collect_python_files(src_root)
    test_files = collect_python_files(tests_root)
    all_files = list(set(src_files) | set(test_files))

    module_to_file = build_module_to_file_map(all_files, src_root)
    reverse_graph = build_reverse_dep_graph(all_files, module_to_file, src_root)

    impacted = transitive_closure(set(changed_files), reverse_graph, module_to_file, src_root)
    test_subset = filter_to_test_files(impacted, tests_root)

    for t in test_subset:
        print(t)

    print(
        f"# {len(test_subset)} test(s) impacted "
        f"(out of {len(test_files)} total — "
        f"{int(100 * (1 - len(test_subset) / max(1, len(test_files))))}% reduction)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
