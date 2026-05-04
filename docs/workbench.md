# Locus workbench

A browser-based playground for every locus pattern. Pick a tutorial
on the left, paste your model key once, hit **Run**, and watch a real
agent stream events back. No CLI, no `pip install`, no editor setup.

![locus workbench](img/workbench.gif)

## What it is

The workbench is the fastest way to *see* what locus does without
installing anything locally. It's a single-page UI in front of every
canonical locus pattern — a basic agent, an agent with tools, a
structured-output schema, an orchestrator with specialists, a
sequential pipeline, a map-reduce fan-out, a critic loop with
`allow_cycles`. Each pattern is wired to a real Python coroutine
that imports locus, builds the agent, and streams events through to
your browser.

It's also the canonical demo for Codespaces and Docker: visitors
arrive at this app, pick a workflow, and learn the SDK by running
real ones.

```
┌───────────────────────────────────────┐
│  sandbox/web   — vanilla TS + Vite    │  :5173
│  Tutorial catalog · provider settings │
└───────────────────┬───────────────────┘
                    │ /api/*
                    ▼
┌───────────────────────────────────────┐
│  sandbox/bff   — Node Express         │  :3101
│  Same-origin proxy + cookie surface   │
└───────────────────┬───────────────────┘
                    │ /api/*
                    ▼
┌───────────────────────────────────────┐
│  sandbox/backend — FastAPI runner     │  :8100
│  One endpoint per locus pattern       │
└───────────────────────────────────────┘
```

You paste your provider key once per tab — **the workbench never
persists API keys to localStorage**, so closing the tab discards
everything.

## Two paths to spin it up

Pick whichever fits.

### Path A — GitHub Codespaces (zero install, free)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/oracle-samples/locus?devcontainer_path=.devcontainer%2Fdevcontainer.json)

Click the badge on the [repo home page](https://github.com/oracle-samples/locus).
GitHub provisions a Linux container in your account, runs
`.devcontainer/postCreate.sh` to install Python + Node deps, then
forwards port 5173 publicly. ~2-min cold start. You burn your own
free Codespaces minutes (60 hrs/month), nothing on the locus side.

### Path B — Docker (local, BYO key)

```bash
git clone https://github.com/oracle-samples/locus.git && cd locus
docker build -t locus-workbench -f sandbox/Dockerfile .
docker run --rm -p 5173:5173 -p 3101:3101 -p 8100:8100 locus-workbench
# open http://localhost:5173
# → paste OpenAI / Anthropic key in Provider settings → Run a tutorial
```

Image is ~1.3 GB on first build (Oracle Linux 9-slim base + Python
3.12 + Node 20 + locus + the workbench source). Subsequent builds
hit the layer cache.

## Codespaces — what to expect step by step

1. Click the badge above (or [this link](https://codespaces.new/oracle-samples/locus?devcontainer_path=.devcontainer%2Fdevcontainer.json)).
2. Wait ~2 minutes for `.devcontainer/postCreate.sh` to install
   Python deps + npm deps and `.devcontainer/postStart.sh` to boot
   the three tiers.
3. The **Ports** panel pops up in VS Code; click the URL next to
   *5173 (Workbench UI)*. A new tab opens.
4. Click **Provider settings** → paste an OpenAI or Anthropic key →
   Save.
5. Pick a tutorial in the sidebar → **Run**.

The OCI options in the Provider settings modal will not work in
Codespaces — they need a local `~/.oci/config` that doesn't exist
in the container. Use OpenAI or Anthropic for the cloud demo path.

## Docker — port-remap if 5173 is taken

```bash
docker run --rm \
  -p 5273:5173 -p 3201:3101 -p 8200:8100 \
  locus-workbench
# then http://localhost:5273
```

Stop with `Ctrl-C`; `--rm` removes the container automatically.

## Path C — From source (development)

For iterating on the workbench itself:

```bash
git clone https://github.com/oracle-samples/locus.git
cd locus
pip install -e ".[server,oci,openai,anthropic]"  # core + extras

# Three terminals, one per tier:
cd sandbox/bff && npm install && npm run dev      # :3101
cd sandbox/web && npm install && npm run dev      # :5173
cd sandbox/backend && python -m uvicorn --app-dir . runner:app --port 8100
```

Or use the `Makefile` in `sandbox/`:

```bash
cd sandbox && make install
make backend   # in pane 1
make bff       # in pane 2
make web       # in pane 3
```

## Provider settings

The header's **Provider settings** modal accepts four shapes:

- **OpenAI** — paste `sk-…` + pick a model (defaults to `gpt-5.5`).
- **Anthropic** — paste `sk-ant-…` + pick a model
  (defaults to `claude-sonnet-4-6`).
- **OCI session token** — `profile` (e.g. `BOAT-OC1`) +
  `compartment_id` + `region`. Reads `~/.oci/config` at runtime;
  needs a valid session token. Local-machine only.
- **OCI api-key** — same shape, different OCI auth type. Local-machine
  only.

Settings live in the page's memory. Closing the tab discards them.
Reopening the page = paste again. This is intentional: an API key
sitting in `localStorage` on a shared computer is a leak waiting to
happen.

## What you can run

The catalog populates from the BFF's `/api/tutorials` endpoint, which
walks `examples/tutorial_*.py`. As of writing the workbench has 7
patterns wired through dedicated FastAPI endpoints (basic agent,
agent + tools, structured output, orchestrator + specialists,
sequential composition, map-reduce, critic loop) and the rest run as
plain Python subprocesses against your provider — same behaviour as
running the tutorial from a terminal, just inside the workbench so
you can watch streamed events instead of tailing stdout.

## Cost

**You pay $0** when someone uses the workbench. Each visitor's
compute hits their own free GitHub / their own Docker, and their
model calls hit their own provider key. Oracle pays $0 unless an
oracle-employee opens it AND `oracle-samples` org Codespaces billing
is enabled.

## Troubleshooting

- **Sidebar is empty** — BFF couldn't reach the backend. Check
  `docker logs <container>` or the runner pane: usually means the
  backend hasn't finished starting yet (10-20s on cold boot).
- **"Provider settings: setup required" never goes away** — you
  closed the modal without hitting Save. Reopen and click Save.
- **OCI session-token auth says "no profile"** — you're running in
  Codespaces / Docker; OCI auth needs `~/.oci/config` mounted in.
  Switch to OpenAI or Anthropic.
- **Tutorial fails with "no parsed Pydantic" / empty output** — your
  model is too small for structured output. Use `gpt-5.5-2026-04-23`,
  `gpt-4o`, or `claude-sonnet-4-6` for the demos that use
  `output_schema`.
