# Contributing to locus

Thank you for your interest in contributing. Whether it's a bug
report, a new feature, a documentation correction, or a one-line
typo fix — feedback and contributions from the community are how this
project gets better.

Please read this document end-to-end before opening an issue or PR.
It exists so we can spend our time reviewing the substance of your
contribution instead of asking for missing context.

## Table of contents

- [Reporting bugs and feature requests](#reporting-bugs-and-feature-requests)
- [Finding contributions to work on](#finding-contributions-to-work-on)
- [Development tenets](#development-tenets)
- [Development environment](#development-environment)
- [Coding standards](#coding-standards)
- [Tests — mandatory, no exceptions](#tests--mandatory-no-exceptions)
- [Documentation](#documentation)
- [Contributing via pull requests](#contributing-via-pull-requests)
- [Commit messages — Conventional Commits](#commit-messages--conventional-commits)
- [Code of Conduct](#code-of-conduct)
- [Oracle Contributor Agreement](#oracle-contributor-agreement)
- [Security issue reporting](#security-issue-reporting)
- [Licensing](#licensing)

## Reporting bugs and feature requests

Use the issue templates:

- [**Bug Report**](../../issues/new?template=bug_report.yml) — for
  reproducible defects.
- [**Feature Request**](../../issues/new?template=feature_request.yml)
  — for new capabilities or design proposals.

Before filing a new issue, please check the existing trackers:

- [Open bugs](../../issues?q=is%3Aissue+is%3Aopen+label%3Abug)
- [Open feature requests](../../issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)
- [Recently merged PRs](../../pulls?q=is%3Apr+is%3Aclosed)

A good bug report contains:

- A reproducible test case (a failing snippet, a specific tutorial,
  or steps to reproduce).
- The locus version (`pip show locus` → `Version` field).
- The model id and provider (e.g. `oci:openai.gpt-5.5`).
- Any modifications you've made to the example you're running.
- The full error / traceback. *Not* a screenshot of part of it.

## Finding contributions to work on

Issues we've vetted as ready for community contribution carry the
[`ready for contribution`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22ready+for+contribution%22)
label. Start there.

Before starting non-trivial work:

1. Check the issue isn't already assigned or in-progress.
2. Comment on the issue saying you'd like to work on it and ask any
   clarifying questions.
3. Wait for a maintainer to confirm before spending serious time on
   it. We hate seeing your weekend's work end up in a "we already
   have this" reply.

For one-line fixes — typos, broken links, missing imports — go ahead
and open the PR directly.

## Development tenets

These principles guide every design decision in locus. When in doubt
about an API choice, refer back to these. PR reviewers will too.

1. **Production agents fail in predictable ways. Make the failure
   mode boring.** Idempotency, durable memory, composable termination,
   self-correcting loops — these aren't features, they're the
   boilerplate every production agent needs. We ship the boilerplate
   so applications can be small.
2. **The obvious path is the happy path.** Through naming, types, and
   defaults, we guide developers toward correct patterns and away from
   common pitfalls. If the example needs a paragraph of "but be
   careful…", the API is wrong.
3. **Native, not adapter.** Every backend (model provider, checkpointer,
   vector store, hook) implements one Protocol contract directly. No
   `Saver`-wraps-`Saver`-wraps-callable indirection.
4. **Composability is non-negotiable.** Termination conditions compose
   with `&` and `|`. Multi-agent shapes mix in one process. Hooks chain
   without surprises. Each primitive is built knowing every other
   primitive is in the room.
5. **Typed values, plain runtime.** State, events, configs, and tool
   inputs/outputs are typed value objects. The runtime nodes that act
   on them are not. Pydantic is plumbing, not a religion.
6. **Day-0 OCI Generative AI.** When OCI ships a new model id, locus
   already supports it. We never ask you to wait on a provider PR.
7. **Small enough to read.** A senior Python engineer should be able to
   read `src/locus/` end-to-end in an afternoon. We resist abstractions
   that don't earn their keep.

## Development environment

### Prerequisites

- **Python 3.11+** (3.11 and 3.12 supported).
- **[Hatch](https://hatch.pypa.io/)** for environment + script
  management.
- **Git** ≥ 2.30.

### Setting up

```bash
git clone https://github.com/oracle-samples/locus.git
cd locus

# Install Hatch if you don't have it
pip install --user hatch

# Create the dev environment (deps + the package in editable mode)
hatch env create

# Install pre-commit + commit-msg hooks — required, see below
pip install pre-commit
pre-commit install -t pre-commit -t commit-msg

# Verify the setup — should be green
hatch run all
```

### The hatch scripts you actually use

| Script | What it runs |
|---|---|
| `hatch run all` | Format · lint · mypy strict · 2,987 unit tests. The single command that has to pass before any PR. |
| `hatch run format` | `ruff format src tests` (line length 100). |
| `hatch run lint` | `ruff check src tests`. |
| `hatch run lint-fix` | Same with `--fix`. |
| `hatch run typecheck` | `mypy src/locus` strict. |
| `hatch run test` | Unit tests only (`tests/unit/`). |
| `hatch run test-fast` | Unit tests parallel (`pytest -n auto`). |
| `hatch run test-cov` | Coverage HTML at `htmlcov/index.html`. |
| `hatch run pytest tests/integration -v` | Integration tests (skip cleanly when their service isn't reachable). |
| `hatch run docs:serve` | Local docs at <http://127.0.0.1:8000>. |
| `hatch run docs:build` | Static `site/` directory. |

### Pre-commit hooks (required)

We use [pre-commit](https://pre-commit.com/) to enforce quality
*before* CI ever sees the code. The hook chain runs on every commit:

- `ruff format` — formatter
- `ruff check` — linter
- `mypy --strict` — type checker
- `markdownlint` — Markdown
- `commitizen check` — Conventional-Commit message format
- `gitleaks` — secret detection
- `large-files` — 1,000 KB max per file
- `pretty-format-yaml` — YAML normalisation

A failed hook always tells you the exact fix. Don't bypass with
`--no-verify`. Open an issue if a hook is wrong; don't paper over it.

## Coding standards

### Style

- **Line length 100.**
- **Type hints required** on every public function, method, and class
  attribute. mypy runs strict.
- **Google-style docstrings** on every public symbol. Short on intent;
  longer on subtle constraints.
- **No bare `Any` in public signatures.** Internal helpers can use
  `Any` sparingly; public APIs cannot.
- **No `print` in library code.** Use the `LoggingHook` /
  `StructuredLoggingHook` or stream events.

### Architecture

- **Typed data, plain classes for behavior.** State, events, configs,
  and tool I/O are typed value objects. The runtime nodes that act on
  them are not.
- **Immutable state.** State updates return a new instance via
  `state.with_message(...)` / `state.with_metadata(...)`. Hooks see
  frozen events.
- **Async-native.** Public APIs are async-first; sync wrappers
  (`run_sync`) exist where ergonomic but never the other way round.
- **Protocol-based interfaces.** `BaseCheckpointer`, `ModelProtocol`,
  `BaseEmbedder`, `VectorStore` are runtime-checkable Protocols. New
  backends implement the Protocol — no inheritance.
- **Explicit over implicit.** No registries that auto-discover from
  disk, no import-time side effects. Providers register themselves
  through an explicit call.

### File layout

A new top-level capability looks like:

```text
src/locus/<capability>/
    __init__.py     # public exports
    base.py         # the Protocol / abstract base
    <impl>.py       # concrete implementations (one per backend)
    config.py       # typed config models
tests/unit/<capability>/
    test_<impl>.py  # one test file per implementation
```

## Tests — mandatory, no exceptions

**Every PR that changes behavior must include tests.** This is not
negotiable. PRs without tests will be sent back regardless of how
small the change "looks".

The bar — and what reviewers will check:

### What requires a test

| Change | Required test |
|---|---|
| New public function or class | Unit test covering the public contract — happy path + at least one error path. |
| New `@tool`, hook, or Protocol implementation | Unit test using the registered fixtures. |
| New checkpointer, vector store, or model provider | Unit test against the in-memory mock + integration test against the real backend (gated by env var). |
| Bug fix | Failing test reproducing the bug, then the fix. The test should fail without the fix and pass with it. |
| Refactor / rename / move | Existing tests must pass unchanged. If they don't, the refactor is changing behavior — write tests for the new behavior. |
| Documentation only | No test required. |
| Tutorials in `examples/` | The tutorial must run end-to-end; integration smoke test if it touches a real service. |

### What "covered" means

- **Happy path** — the function returns the right value for
  representative input.
- **Boundary** — empty inputs, single-element inputs, max-allowed
  inputs.
- **Error path** — the function raises (or surfaces) the documented
  error class for the documented bad inputs.
- **Side effects** — if the function persists state, calls a hook, or
  emits an event, the test asserts that.

A test that asserts only `assert result is not None` is not a test.
It's a syntax check.

### Where tests live

- `tests/unit/` — no external services, no network. Runs on every
  commit and on every `hatch run all`. Must be deterministic; a
  flaky unit test is a bug.
- `tests/integration/` — real OCI Generative AI, real Oracle 26ai,
  real Object Storage, real Redis, real PostgreSQL, real OpenSearch.
  Skips cleanly when the service is unreachable. Run before
  shipping changes that touch a backend.
- The full env-var matrix for integration tests lives in
  [`tests/integration/conftest.py`](tests/integration/conftest.py).

### Mocks

**Mocks belong in unit tests only.** Integration tests must hit the
real service — the whole point of the integration suite is to catch
divergence between mock semantics and real behavior. If something
cannot be tested without mocks, write the unit test now and add a
`# TODO: integration coverage` comment for the follow-up.

### Pytest markers

| Marker | Meaning |
|---|---|
| `requires_oci` | Needs OCI Generative AI configured. |
| `requires_oracle_26ai` | Needs Oracle Database 26ai with a wallet. |
| `requires_redis` | Needs a reachable Redis. |
| `requires_postgres` | Needs a reachable PostgreSQL. |
| `requires_opensearch` | Needs a reachable OpenSearch. |
| `requires_ollama` | Needs a local Ollama install. |
| `slow` | > 5 seconds; excluded from `hatch run test` by default. |

### Running before you push

```bash
hatch run all                          # mandatory: format + lint + mypy + unit
hatch run pytest tests/integration -v  # required if you changed a backend
```

## Documentation

The [`docs/`](docs/) tree is the source of the project documentation
site (Material for MkDocs). Layout:

```text
docs/
├── index.md            # landing page
├── concepts/           # one idea per file, grouped by capability
├── concepts/multi-agent/  # the seven coordination patterns
├── how-to/             # task-oriented recipes
├── api/                # auto-generated API reference (mkdocstrings)
└── img/                # logo + diagrams
```

When your change touches behavior:

- **New public API** → update or add a `docs/concepts/*.md` page and
  the relevant snippet in `README.md` if it changes the
  five-things-that-make-locus-different shape.
- **New backend** → add a row to the matrix in `docs/FEATURES.md` and
  the corresponding concept page (e.g.
  `docs/concepts/checkpointers.md` for a new memory backend).
- **New top-level capability** → add a row to the "What you get" grid
  in both `README.md` and `docs/index.md`.

Build locally:

```bash
hatch run docs:serve            # http://127.0.0.1:8000, autoreloads
hatch run docs:build            # static site under site/
```

The docs build runs in strict mode (`mkdocs build --strict`) — broken
links fail the build.

## Contributing via pull requests

Before sending a PR:

1. You're working against the latest `main`.
2. You've checked that an open or recent PR doesn't already cover
   the same ground.
3. For non-trivial work, you've opened an issue first to align on the
   approach.

To send the PR:

1. Create a feature branch — `feat/<short-description>`,
   `fix/<short-description>`, `docs/<short-description>`,
   `test/<short-description>`, `chore/<short-description>`. Don't
   push directly to `main`.
2. Make the change. Focus the diff on one concern; if you also
   reformatted the whole file, reviewers can't see what you did.
3. `hatch run all` must pass.
4. Add tests (see [above](#tests--mandatory-no-exceptions)).
5. Update the docs if the public API changed.
6. Commit using [Conventional Commits](#commit-messages--conventional-commits).
7. Push to your fork or branch and open the PR.
8. Pay attention to CI. If a check fails, fix it before asking for
   review — don't pile on commits while CI is red.

### PR description template

The repo's `.github/pull_request_template.md` is the source of truth.
A PR that doesn't fill it in will be sent back. The template asks for:

- **Summary** — what changed and why, in one paragraph.
- **Linked issue** — `Fixes #NNN` or `Refs #NNN`.
- **Notes for reviewer** — anything subtle, any trade-offs, anything
  deliberately *not* in scope.
- **Test plan** — checkboxes for `hatch run all`, integration suite
  if relevant, manual verification of the user-visible behavior.

## Commit messages — Conventional Commits

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <description>

<optional body — wrap at ~72 cols>
```

Accepted types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`,
`ci`, `chore`, `build`. Scopes are usually a top-level subdirectory
of `src/locus/` (`agent`, `memory`, `multiagent`, `rag`, `tools`,
`hooks`, …) or `readme` / `tutorials` for docs commits.

Good:

```text
feat(rag): add Pinecone vector store
fix(memory): release Oracle pool on event-loop close
docs(tutorials): add RAG-with-Oracle-26ai walkthrough
```

The `commitizen` pre-commit hook validates this on every commit; CI
re-validates on every PR.

## Code of Conduct

This project follows the
[Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
By participating you agree to uphold it.

## Oracle Contributor Agreement

Before your first contribution is merged, sign the
[Oracle Contributor Agreement (OCA)](https://oca.opensource.oracle.com).
It's a one-time step; once signed, it covers all future contributions
to any Oracle open-source project. The
[`oca/oracle`](https://oca.opensource.oracle.com/) GitHub check on
every PR verifies your commit author email matches the signers list.

## Security issue reporting

**Do not** open a public GitHub issue for a security vulnerability.

Email reports to [secalert_us@oracle.com](mailto:secalert_us@oracle.com),
preferably with a proof of concept. See
[Oracle's security vulnerability reporting page](https://www.oracle.com/corporate/security-practices/assurance/vulnerability/reporting.html)
for the full process.

## Licensing

locus is released under the
[Universal Permissive License v1.0](LICENSE.txt). By submitting a
contribution you agree that your contribution is licensed under the
same terms.

---

Thanks for contributing. Small, surgical PRs with tests are how locus
stays sharp.
