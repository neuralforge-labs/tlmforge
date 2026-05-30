# tlmforge: generate-architecture

Bootstrap or rebuild `docs/ARCHITECTURE.md` — the living architecture document
that Stage A of the feature-development skill reads to scope its updates.

Run this once when starting a new project, or whenever you want to rebuild the
full architecture picture from scratch (e.g., after a major refactor).

---

## When to use

- **First run on a new project** — `docs/ARCHITECTURE.md` doesn't exist yet
- **Explicit rebuild** — user invokes `/tlmforge:generate-architecture`
- **Drift catch-up** — `last-updated-commit` has fallen far behind HEAD and
  Stage A's scoped updates aren't keeping pace

After the first scan, Stage A in feature-development handles incremental updates
automatically. You don't need to re-run this skill unless you want a full rebuild.

---

## What it produces

`docs/ARCHITECTURE.md` — a living document with:

1. **Header block** — machine-readable metadata used by Stage A
2. **Component index** — maps component names to canonical file paths
3. **Per-component sections** — description, key interfaces, internal dependencies

---

## The scan procedure

### Step 1 — Identify components

A component is a cohesive unit of functionality. Use this priority order —
stop at the first tier that gives you a clear component list:

**Tier 1 (preferred):** Package manifests and language entry points —
`package.json` workspaces, `pyproject.toml` / `setup.cfg` packages,
`Cargo.toml` workspace members, `go.work` modules. These are explicit
component boundaries declared by the author.

**Tier 2:** Top-level directories with a self-identification marker — a
README, `__init__.py`, `index.ts`, or `main.*` at the directory root.

**Tier 3 (fallback):** If neither Tier 1 nor Tier 2 yields > 1 candidate,
treat the whole repo as a single component named after the project root.
Invoke `AskUserQuestion` to confirm before writing: "I found only one
candidate component. Is this a monolithic repo, or should I look elsewhere?"

```bash
# Tier 1 check
find . -maxdepth 3 \( -name "package.json" -o -name "pyproject.toml" \
  -o -name "Cargo.toml" -o -name "go.work" \) | head -20

# Tier 2 fallback
ls -d */ 2>/dev/null || find . -maxdepth 1 -type d | sort
```

For each candidate directory:
- Is it a discrete functional unit (auth, payments, API, UI, CLI)?
- Does it have its own README, `__init__.py`, `index.ts`, or `main.*`?
- Is it > 2 files?

If yes: it's a component. If no: merge it with its parent or nearest neighbour.

Skip: `.git/`, `node_modules/`, `venv/`, `__pycache__/`, `.claude/`,
`specs/`, `docs/`, `tests/` (these are support dirs, not components).
Exception: a `tests/` that contains test doubles or fixtures that other
components import IS a component.

### Step 2 — For each component, read key files

Read entry files only — don't read every file:
- Entry files: `__init__.py`, `index.ts/js`, `main.py/go/rs`, `mod.rs`,
  `app.py`, `server.py`, `router.py`, `routes.py`
- Interface files: `types.ts`, `models.py`, `schema.py`, `api.py`
- Config files at the component root: `config.py`, `settings.py`, `*.yaml`

For larger components (>20 files), also read 2-3 files that appear most-imported
by other components (use `grep -r "from <component>" --include="*.py" -l | head -5`
or equivalent).

### Step 3 — Write docs/ARCHITECTURE.md

Use this exact format — Stage A parses the header fields and component index:

```markdown
# <Project name> — Architecture
<!-- tlmforge-architecture-doc: v1 -->
last-updated-commit: <full 40-char SHA from `git rev-parse HEAD`>
last-full-scan-commit: <same SHA on first run>
verified-at-commit: <same SHA on first run>
scan_status: COMPLETE

## Component index
<!-- Stage A uses this table to map file paths to component names. -->
<!-- Add every canonical file/directory that belongs to each component. -->
| Component | Canonical paths |
|---|---|
| <name> | <path1>, <path2> |
| ... | ... |

---

## <Component: name>

**What it does:** <1-2 sentences>

**Key files:**
- `path/to/entry.py` — <role>
- `path/to/types.py` — <role>

**Exposes:**
- `FunctionName(args) → return_type` — <purpose>
- `ClassName` — <purpose>

**Depends on:** <other component names, or "none">

**Key flows:**
```
<brief ASCII sequence or bullet list of the main interaction>
```

**Notes:** <anything surprising, non-obvious invariants, known limitations>

---

## <Component: name2>
...
```

### Step 4 — Emit a summary

After writing the file, print:

```
docs/ARCHITECTURE.md written.
  Components found: N
  Commit anchored: <short SHA>
  Lines: <line count>

To update a specific component: edit the relevant section and run
  git rev-parse HEAD
then update last-updated-commit manually, or let Stage A do it on the
next feature-development run.
```

---

## Handling large repos

If the repo has >50 top-level directories or >500 files, limit the initial
scan to: entry files + files that are imported by >3 other files. Set
`scan_status: PARTIAL` in the header and add a banner at the top of
ARCHITECTURE.md:

```markdown
> **Partial scan** — only entry files and cross-imported interfaces were
> read. Run `/tlmforge:generate-architecture` again to read all files.
```

Stage A reads `scan_status` to decide whether drift detection is reliable:
- `COMPLETE`: full drift detection via component index
- `PARTIAL`: Stage A falls back to full re-scan on any detected change

---

## Incremental vs. full rebuild

This skill always does a **full rebuild** — it overwrites `docs/ARCHITECTURE.md`
completely. Stage A in feature-development does incremental updates (scoped to
the components touched by the current task). Use this skill when you want a
clean slate, not Stage A's incremental path.

---

## docs/ARCHITECTURE.md header field semantics

| Field | Set by | Meaning |
|---|---|---|
| `last-updated-commit` | Stage A (feature-development) | Last commit where any component section was actually rewritten |
| `last-full-scan-commit` | generate-architecture | Last commit where the full repo was scanned |
| `verified-at-commit` | Stage A (feature-development) | Last commit where Stage A ran and confirmed no update was needed |
| `scan_status` | generate-architecture | `COMPLETE` if all files were read; `PARTIAL` if the large-repo limit was hit |

Stage A uses `last-updated-commit` to compute the diff range when checking for
drift. If `verified-at-commit` == HEAD, Stage A skips the diff entirely (already
up to date).

---

## Drift detection (Stage A reads this)

After writing, Stage A knows which components exist and which file paths belong to
each (from the component index table). When Stage A runs on a subsequent feature:

1. Compute `git diff <last-updated-commit>..HEAD --name-only`
2. For each changed file: look up its component in the index
3. If the component exists: mark it stale
4. If the file doesn't match any component: create a new component section
5. Update only stale sections; set `last-updated-commit` = HEAD

If `last-updated-commit` is missing or the diff is too large (>200 files): fall
back to a full re-scan (call generate-architecture logic inline).
