# Contributing to Locus

Thank you for your interest in contributing! Locus aims to be a small, sharp,
production-grade SDK — every change should leave the project a little crisper
than it found it. The points below are how we keep that bar.

- [Quick contributor flow](#quick-contributor-flow)
- [Code of Conduct](#code-of-conduct)
- [Oracle Contributor Agreement](#oracle-contributor-agreement)
- [Development setup](#development-setup)
- [Branches and commits](#branches-and-commits)
- [What `hatch run all` actually runs](#what-hatch-run-all-actually-runs)
- [Coding standards](#coding-standards)
- [Tests — unit, integration, services](#tests--unit-integration-services)
- [Documentation](#documentation)
- [Pull requests](#pull-requests)
- [Release checklist](#release-checklist)
- [Where to ask](#where-to-ask)

## Quick contributor flow

```bash
git clone https://github.com/oracle-samples/locus.git
cd locus
pip install hatch
hatch env create

pre-commit install                  # optional but recommended
hatch run all                       # format + lint + mypy + 2,987 unit tests, ~6 s

git checkout -b feat/my-thing
# … edit, test, commit …
hatch run all                       # green before you push
git push -u origin feat/my-thing    # then open a PR
```

That's the loop. Everything else in this file is the *why* behind each step.

## Code of Conduct

This project follows the
[Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
By participating, you agree to uphold it.

## Oracle Contributor Agreement

Before your first contribution is merged, sign the
[Oracle Contributor Agreement (OCA)](https://oca.opensource.oracle.com).
It's a one-time step; once signed it covers all future contributions.

Every commit must carry a sign-off line:

```text
Signed-off-by: Your Name <your.email@example.com>
```

Use `git commit -s` (or `git commit --signoff`) and Git appends it for you.

## Development setup

### Prerequisites

- **Python 3.11+** (the test matrix runs on 3.11 and 3.12).
- **[Hatch](https://hatch.pypa.io/)** for environments, scripts, and packaging.
- **Git** with a recent enough version to support sparse-checkout if you only
  want a subset of the tests.

### Environments

`hatch env create` builds the default environment with the `dev` and `all`
extras (every model provider, every checkpointer backend, every vector store).
Subsequent `hatch run …` calls reuse that environment.

The other environments are:

| Env | What it gives you |
|---|---|
| `default` | Everything — the one you want most of the time. |
| `test` | Same as default; convenient for `hatch run test:test`. |
| `docs` | Material for MkDocs + `mkdocstrings` (`hatch run docs:serve`). |

### Pre-commit hooks

```bash
pip install pre-commit
pre-commit install
```

Configured hooks (see `.pre-commit-config.yaml`):

- `check-added-large-files` — 1,000 KB cap (rendered media must live elsewhere).
- `ruff` — lint and format.
- `mypy` — strict.
- `markdownlint` — trailing-blank rules.
- `commitizen` — Conventional-Commit message check.
- `detect-secrets` — fails on plausible credentials.

The hooks run on `pre-commit`. A failed hook always tells you the exact fix; do
not bypass with `--no-verify`.

## Branches and commits

### Branch naming

```text
feat/<short-description>
fix/<short-description>
docs/<short-description>
test/<short-description>
chore/<short-description>
```

Examples: `feat/pinecone-store`, `fix/checkpoint-concurrent-write`,
`docs/rag-tutorial`.

Branch from `main`. Don't push to `main` directly — the
`no-commit-to-branch` pre-commit hook blocks it locally and the remote enforces
the same rule.

### Conventional Commits

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <description>

<optional body — wrap at ~72 cols>

Signed-off-by: Your Name <email>
```

Types we accept: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `ci`,
`chore`, `build`. Scopes are usually a top-level subdirectory of `src/locus/`
(`agent`, `memory`, `multiagent`, `rag`, `tools`, `hooks`, …) or `readme` /
`tutorials` for docs commits.

Good:

```text
feat(rag): add Pinecone vector store
fix(memory): release Oracle pool on event-loop close
docs(tutorials): add RAG-with-Oracle-26ai walk-through
```

Less good — too vague (`fix: bug`, `feat: stuff`) or two changes in one commit.
Split unrelated changes into separate commits.

## What `hatch run all` actually runs

`hatch run all` is the single command that has to pass before a PR is ready.
It chains four steps in order:

| Step | Script | What it does |
|---|---|---|
| 1. | `hatch run format` | `ruff format src tests` (line length 100). |
| 2. | `hatch run lint-fix` | `ruff check --fix src tests` — autofix safe lints. |
| 3. | `hatch run typecheck` | `mypy src/locus` in strict mode. |
| 4. | `hatch run test` | `pytest tests/` — 2,987 unit tests, ~6 s on a laptop. |

Other useful scripts:

```bash
hatch run lint           # ruff check, no autofix
hatch run format-check   # check-only, never writes
hatch run test-fast      # pytest -n auto  (parallel)
hatch run test-cov       # coverage HTML at htmlcov/
hatch run docs:serve     # local docs site at http://127.0.0.1:8000
```

## Coding standards

### Style

- **Line length 100.**
- **Type hints required** on every public function, method, and class
  attribute. `mypy` runs strict.
- **Google-style docstrings** on every public symbol. Short on intent, longer
  on subtle constraints.
- **No bare `Any` in signatures.** Internal helpers can use `Any`; public APIs
  cannot.
- **No prints in library code.** Use the `LoggingHook` /
  `StructuredLoggingHook` or the streaming events.

### Architecture

These are conventions, not religion — but deviate only with a clear reason:

1. **Typed data, plain classes for behavior.** State, events, configs, and
   tool inputs/outputs are typed value objects; the runtime nodes that act
   on them are not.
2. **Immutable state.** State updates return a new instance via
   `state.with_message(...)` / `state.with_metadata(...)`. Hooks see frozen
   events.
3. **Async-native.** Public APIs are async-first; sync wrappers (`run_sync`)
   exist where ergonomic but never the other way round.
4. **Protocol-based interfaces.** `BaseCheckpointer`, `BaseModel`,
   `BaseEmbedder`, `VectorStore` are runtime-checkable `Protocol`s. New
   backends implement the protocol, no inheritance.
5. **Explicit over implicit.** No registries that auto-discover from disk, no
   import-time side effects. New providers register themselves via an explicit
   call.

### File layout

A new top-level capability looks like:

```text
src/locus/<capability>/
    __init__.py     # public exports + version banner if any
    base.py         # the Protocol / abstract base
    <impl>.py       # concrete implementations (one per backend)
    config.py       # typed config models
tests/unit/<capability>/
    test_<impl>.py  # one test file per implementation
```

## Tests — unit, integration, services

### Unit tests

`tests/unit/` — no external services, no network. They run on every commit
and on every `hatch run all`. New code without unit tests will not be merged.

```bash
hatch run test                                    # all units, ~6 s
hatch run pytest tests/unit/agent -v              # one subtree
hatch run pytest tests/unit/agent/test_agent.py::test_run_sync -v
```

### Integration tests

`tests/integration/` — real OCI GenAI, real Oracle 26ai, real Object Storage,
real Redis, real PostgreSQL, real OpenSearch. They skip when their service
isn't available; the skip message tells you which env var to set.

The full env-var matrix lives in [`tests/integration/conftest.py`](tests/integration/conftest.py)
— treat that file as the source of truth. The most common subset:

```bash
export OCI_PROFILE=DEFAULT
export OCI_REGION=us-chicago-1
export OCI_MODEL_ID=openai.gpt-5.5
export REDIS_URL=redis://localhost:6379
export POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
       POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres POSTGRES_DB=locus

hatch run pytest tests/integration -v
```

Local services for integration tests come up via `docker compose` —
see [`TESTING_LOCAL.md`](TESTING_LOCAL.md) for the full setup.

### Pytest markers

| Marker | Meaning |
|---|---|
| `requires_oci` | Needs OCI GenAI configured. |
| `requires_oracle_26ai` | Needs Oracle 26ai with a wallet. |
| `requires_redis` | Needs a reachable Redis. |
| `requires_postgres` | Needs a reachable PostgreSQL. |
| `requires_opensearch` | Needs a reachable OpenSearch. |
| `requires_ollama` | Needs a local Ollama install. |
| `slow` | > 5 s — excluded from `hatch run test` defaults. |

Run a single marker with `hatch run pytest -m requires_oci -v`.

### Mocks

Mocks belong in unit tests only. Integration tests must hit the real service —
the whole point of the suite is to catch divergence between mock semantics
and real behavior. If something cannot be tested without mocks, write the
unit test and add a `# TODO: integration coverage` comment.

## Documentation

The [`docs/`](docs/) tree is the source of the project documentation site
(Material for MkDocs). Layout:

```text
docs/
├── index.md           # site landing page
├── concepts/          # explanations of one idea per file
├── how-to/            # task-oriented recipes
├── reference/         # auto-generated API ref (mkdocstrings)
└── img/               # logo + diagrams (no animated media)
```

Build locally:

```bash
hatch run docs:serve   # http://127.0.0.1:8000, autoreloads
hatch run docs:build   # static site under site/
```

When you add or change behavior:

- **Public API change** → update the relevant `docs/concepts/` page and the
  examples that reference it.
- **New backend** → add a row to the matrix in `docs/FEATURES.md`.
- **New top-level capability** → add a row to the "What you get" grid in
  `README.md` and a short section under "Capabilities, in detail".

## Pull requests

1. **Open an issue first** for non-trivial changes. A two-line "I'm planning to
   …" lets us flag conflicts or steer the design before you spend a weekend
   on it.
2. **One PR, one concern.** Refactors, fixes, and features go in separate PRs
   when they're separable.
3. **Green before you ask for review.** `hatch run all` must pass; CI re-runs
   it on every push.
4. **PR description template:**

   ```markdown
   ## Summary
   One paragraph — what changed and why.

   ## Related issue
   Fixes #NNN

   ## Notes for the reviewer
   - Anything subtle worth flagging
   - Trade-offs you considered
   - Things deliberately *not* in scope

   ## Test plan
   - [ ] `hatch run all` green
   - [ ] Relevant integration suite run locally (or n/a)
   - [ ] Manual verification of <X>
   ```

5. **Review.** A maintainer will respond within a week. Address comments by
   pushing a fixup commit; don't squash before review unless asked. Merge
   commits use the PR title (verify it's still Conventional-Commit-shaped).

## Release checklist

Every release follows this checklist. Don't skip steps.

1. **Update `CHANGELOG.md`.** Move entries from `[Unreleased]` into a new
   version heading dated `YYYY-MM-DD`. Call out breaking changes under
   `### Removed` / `### Changed` with a one-line migration snippet.
2. **Deprecation sweep.** Every removal must have shipped at least one prior
   minor with a `LocusDeprecationWarning` — see
   [`DEPRECATION.md`](DEPRECATION.md) — or document the single-release
   migration path in the CHANGELOG entry.
3. **Version bump.** `__version__` in `src/locus/__init__.py` and the
   `version` field in `pyproject.toml` move together.
4. **Full matrix.** `hatch run all` plus `hatch run pytest tests/integration -v`
   with every backing service available locally.
5. **Tag.** `git tag -a vX.Y.Z -m "Release vX.Y.Z"` and push the tag.
6. **Build & verify.** `hatch build`, then inspect the wheel — no compliance
   artifacts, no fixture data, no `.env` files.
7. **Announce.** The CHANGELOG entry is the release note; deprecations are
   restated in the announcement.

## Where to ask

- **Bug or feature** — open a [GitHub Issue](https://github.com/oracle-samples/locus/issues).
- **Design question** — open a [GitHub Discussion](https://github.com/oracle-samples/locus/discussions).
- **Security report** — see [`SECURITY.md`](SECURITY.md). Do *not* open a public
  issue.

Thanks for contributing — small, surgical PRs with tests are how locus stays
sharp.
