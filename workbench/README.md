# workbench — locus pattern playground

A self-contained 3-tier workbench: **vanilla TypeScript front-end** ↔
**Node BFF** ↔ **Locus Python pattern runner**. Bring your own provider
credentials (OpenAI / Anthropic / OCI session / OCI api-key) — no
instance principals, no external dependencies beyond the model
provider.

```
┌──────────────────────────────────────┐
│  workbench/web — vanilla TS + Vite   │  :5173
│  Pattern catalog · provider settings │
└────────────────┬─────────────────────┘
                 │ /api/*
                 ▼
┌──────────────────────────────────────┐
│  workbench/bff — Node Express        │  :3101
│  Thin proxy + same-origin surface    │
└────────────────┬─────────────────────┘
                 │ /api/*
                 ▼
┌──────────────────────────────────────┐
│  workbench/backend — FastAPI runner  │  :8100
│  One endpoint per locus pattern      │
└──────────────────────────────────────┘
```

## What you can run today

Seven patterns wired so far. Each runs against the provider you set in
the UI. Adding a new one is ~20 lines: write a coroutine + register it
in `PATTERN_RUNNERS`.

| Tutorial | Pattern | Notes |
|---|---|---|
| 01 | Basic agent | One Agent answers |
| 02 | Agent + tools | ReAct loop, two trivial tools |
| 13 | Structured output | Pydantic `output_schema` → typed Verdict |
| 17 | Orchestrator + specialists | Coordinator + 2 specialists |
| 25 | Composition (Sequential) | researcher → summariser |
| 42 | Map-reduce code review | `Send` fan-out to N reviewers, reduce |
| 43 | StateGraph (critic loop) | Writer → Critic with `allow_cycles` |

## Provider auth

The web UI's **Provider settings** modal accepts one of:

- **OpenAI** — `api_key` + `model` (defaults `gpt-5`)
- **Anthropic** — `api_key` + `model` (defaults `claude-sonnet-4-6`)
- **OCI session** — `profile` (any session-token profile in
  `~/.oci/config`, e.g. `MY_PROFILE`) + `compartment_id` + `region`
- **OCI api-key** — same shape, just a different OCI profile type

Settings live in `localStorage` under `locus.workbench.provider`. They're
sent on every request body to the backend; never persisted server-side.

## Run locally

```bash
# 1. Start the python runner (in a venv with locus + the project deps).
cd workbench/backend
PYTHONPATH=../../src \
  uvicorn --app-dir . runner:app --host 127.0.0.1 --port 8100

# 2. Start the BFF.
cd ../bff && npm install && npm run dev

# 3. Start the web app.
cd ../web && npm install && npm run dev

# 4. Open http://localhost:5173 → Provider settings → run.
```

Or via the workbench `Makefile`:

```bash
make install
# in three panes:
make backend   # python runner
make bff       # node BFF
make web       # vite dev server
# fourth pane to run the e2e suite:
make e2e
```

## Tests

`workbench/e2e/` — Playwright + chromium.

```bash
cd workbench/e2e && npm install && npx playwright install chromium
npm test
```

Default config talks to OCI session via the `MY_PROFILE` profile against
your target compartment. Override with env:

```bash
OCI_PROFILE=DEFAULT OCI_REGION=us-chicago-1 \
OCI_COMPARTMENT=ocid1.compartment.oc1..xxxxx \
  npm test
```

## Adding a new pattern

`workbench/backend/runner.py`:

1. Write `async def _run_<id>(req: RunRequest) -> RunResponse:` —
   build agents/graph from `req.provider` and call `_drive_agent` /
   `_drive_pipeline`.
2. Add an entry to the `PATTERNS` list (id, title, tutorial #, summary).
3. Register the runner in `PATTERN_RUNNERS`.

The web app will pick it up automatically on next refresh — the
catalog is fetched live from `/api/patterns`.
