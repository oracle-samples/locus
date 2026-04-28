# Oracle 26ai end-to-end demo

A real, runnable agent that exercises every layer of the locus stack
against live Oracle services. No mocks except the email tool, which
falls back to a mock send when Gmail credentials aren't set.

## What it shows

| Layer | Service | Locus class |
|---|---|---|
| Reasoning | OCI GenAI (`openai.gpt-5.5`) | `Agent(reflexion=True)` |
| Skill loading | Filesystem | `Skill.from_file(...)` |
| Embeddings | OCI GenAI (`cohere.embed-english-v3.0`) | `OCIEmbeddings` |
| Vector retrieval | **Oracle 26ai** native `VECTOR` | `OracleVectorStore` |
| Idempotent write | `@tool(idempotent=True)` | `email_report` |
| Durable memory | OCI Object Storage | `OCIBucketBackend` |

## Files

- [`demo.py`](demo.py) — the agent program. ~125 lines.
- [`setup_corpus.py`](setup_corpus.py) — one-shot ingest of five
  sample documents. Idempotent: re-running is a no-op if the
  table is populated.
- [`skills/researcher/SKILL.md`](skills/researcher/SKILL.md) — the
  AgentSkills.io-compliant skill the agent loads.
- [`demo.gif`](demo.gif) — recorded run against the live free-tier
  ADB.

## Pre-reqs

```bash
pip install "locus[oci,oracle]"
```

You need:

- An OCI tenancy with [GenAI service](https://docs.oracle.com/en-us/iaas/Content/generative-ai/home.htm)
  in `us-chicago-1` (or another GenAI region).
- An [Autonomous Database 26ai](https://docs.oracle.com/en-us/iaas/autonomous-database-shared/index.html)
  with the wallet downloaded locally.
- An OCI Object Storage bucket for checkpoints (or change the demo
  to use any other locus checkpointer backend — see
  [`docs/concepts/checkpointers.md`](../../../docs/concepts/checkpointers.md)).

## Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `OCI_PROFILE` | `DEFAULT` | Profile in `~/.oci/config` |
| `OCI_GENAI_REGION` | `us-chicago-1` | Region for GenAI inference |
| `OCI_NAMESPACE` | *required* | Object Storage namespace |
| `OCI_BUCKET_NAME` | `locus-test-checkpoints` | Checkpointer bucket |
| `ORACLE_DSN` | `deepresearch_low` | TNS alias from your wallet |
| `ORACLE_USER` | `ADMIN` | DB user |
| `ORACLE_PASSWORD` | *required* | DB password |
| `ORACLE_WALLET` | `~/.oci/wallets/deepresearch` | Wallet directory |
| `ORACLE_TABLE` | `LOCUS_DEMO_DOCS` | Vector table name |
| `GMAIL_USER` | *(unset → mock)* | SMTP login |
| `GMAIL_APP_PASSWORD` | *(unset → mock)* | Gmail [App Password](https://myaccount.google.com/apppasswords) |

## Run it

```bash
# 1. Set the required env vars
export OCI_PROFILE=DEFAULT
export OCI_NAMESPACE=<your-namespace>
export ORACLE_PASSWORD=<your-adb-admin-password>
export ORACLE_WALLET=$HOME/.oci/wallets/<your-wallet>

# 2. One-time corpus ingest
python setup_corpus.py

# 3. Run the agent
python demo.py
```

Expected output:

```
→ Oracle AI Database 26ai Enterprise Edition Release 23.26.2.1.0 - Production
→ LOCUS_DEMO_DOCS: 5 rows · VECTOR(1024, FLOAT32)


💭 [iter 1] plan: skills
🔧 skills(skill_name='researcher')
↻ reflexion: new_findings (confidence 0.15)

💭 [iter 2] plan: search_corpus
🔧 search_corpus(topic='HNSW', limit=3)
   ↳ Oracle 26ai → id=hnsw       score=0.799
   ↳ Oracle 26ai → id=embeddings score=0.565
   ↳ Oracle 26ai → id=ivf        score=0.558
↻ reflexion: new_findings (confidence 0.26)

💭 [iter 3] plan: email_report
🔧 email_report(to='me@org.com', subject='HNSW brief', body='…')
   ↳ email mock → 'me@org.com' (545 chars)
↻ reflexion: on_track (confidence 0.34)

✓ Sent a 2-sentence HNSW summary citing "hnsw," "embeddings," and "ivf" to me@org.com.
```

## Re-record the GIF

The GIF was made with [VHS](https://github.com/charmbracelet/vhs):

```bash
brew install vhs neovim
cd examples/demos/oracle_26ai
vhs demo.tape
```

`demo.tape` is the source — fork it for your own walkthrough.
