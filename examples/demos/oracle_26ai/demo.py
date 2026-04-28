"""Locus + Oracle 26ai — end-to-end demo.

What this program does in one ``agent.run()``:
  • loads the ``researcher`` skill from disk
  • search_corpus → Oracle 26ai native VECTOR similarity
  • Reflexion self-evaluation each iteration
  • email_report is @tool(idempotent=True)
  • every step checkpointed to OCI Object Storage

Everything is env-driven — no hardcoded credentials or paths.
"""

from __future__ import annotations

import asyncio
import json
import os
import smtplib
import textwrap
import uuid
from email.mime.text import MIMEText
from pathlib import Path

import oracledb

from locus import Agent
from locus.core.events import (
    ReflectEvent,
    TerminateEvent,
    ThinkEvent,
    ToolCompleteEvent,
    ToolStartEvent,
)
from locus.memory.backends.oci_bucket import OCIBucketBackend
from locus.rag import OCIEmbeddings, OracleVectorStore, RAGRetriever
from locus.skills import Skill
from locus.tools.decorator import tool


# ─── Configuration ─────────────────────────────────────────────────────────
# OCI
PROFILE = os.environ.get("OCI_PROFILE", "DEFAULT")
GENAI_REGION = os.environ.get("OCI_GENAI_REGION", "us-chicago-1")
GENAI_ENDPOINT = f"https://inference.generativeai.{GENAI_REGION}.oci.oraclecloud.com"

# Oracle 26ai
ORACLE_DSN = os.environ.get("ORACLE_DSN", "deepresearch_low")
ORACLE_USER = os.environ.get("ORACLE_USER", "ADMIN")
ORACLE_PW = os.environ["ORACLE_PASSWORD"]
ORACLE_WALLET = os.environ.get("ORACLE_WALLET", os.path.expanduser("~/.oci/wallets/deepresearch"))
TABLE = os.environ.get("ORACLE_TABLE", "LOCUS_DEMO_DOCS")

# OCI Object Storage (checkpointer)
BUCKET = os.environ.get("OCI_BUCKET_NAME", "locus-test-checkpoints")
NAMESPACE = os.environ["OCI_NAMESPACE"]


# ─── Vector store + embeddings ─────────────────────────────────────────────
retriever = RAGRetriever(
    embedder=OCIEmbeddings(
        model_id="cohere.embed-english-v3.0",
        profile_name=PROFILE,
        service_endpoint=GENAI_ENDPOINT,
    ),
    store=OracleVectorStore(
        dsn=ORACLE_DSN,
        user=ORACLE_USER,
        password=ORACLE_PW,
        wallet_location=ORACLE_WALLET,
        wallet_password=ORACLE_PW,
        dimension=1024,
        table_name=TABLE,
    ),
)


# ─── Tools ─────────────────────────────────────────────────────────────────
@tool
def search_corpus(topic: str, limit: int = 3) -> list[dict]:
    """Search the Oracle 26ai corpus."""
    rs = asyncio.run(retriever.retrieve(topic, limit=limit))
    return [
        {"id": r.document.id, "content": r.document.content, "score": round(r.score, 3)}
        for r in rs.documents
    ]


@tool(idempotent=True)
def email_report(to: str, subject: str, body: str) -> dict:
    """Send the brief. Idempotent — re-fires return the cached receipt."""
    user, pw = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    if user and pw:
        msg = MIMEText(body)
        msg["Subject"], msg["From"], msg["To"] = subject, user, to
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pw)
            s.sendmail(user, [to], msg.as_string())
        return {"via": "gmail", "to": to, "chars": len(body)}
    return {"via": "mock", "to": to, "chars": len(body)}


# ─── Agent ─────────────────────────────────────────────────────────────────
agent = Agent(
    model="oci:openai.gpt-5.5",
    tools=[search_corpus, email_report],
    skills=[Skill.from_file(Path(__file__).parent / "skills" / "researcher")],
    reflexion=True,
    checkpointer=OCIBucketBackend(
        bucket_name=BUCKET,
        namespace=NAMESPACE,
        profile_name=PROFILE,
    ),
    system_prompt=(
        "You are a research assistant. Before every tool call, write one "
        "short sentence explaining what you're about to do and why. "
        "Then call the tool. Use the available skill."
    ),
)


# ─── Run ───────────────────────────────────────────────────────────────────
def preflight() -> None:
    """Open a real Oracle 26ai connection so the version banner is visible."""
    with oracledb.connect(
        user=ORACLE_USER,
        password=ORACLE_PW,
        dsn=ORACLE_DSN,
        config_dir=ORACLE_WALLET,
        wallet_location=ORACLE_WALLET,
        wallet_password=ORACLE_PW,
    ) as conn:
        cur = conn.cursor()
        cur.execute("SELECT banner_full FROM v$version")
        banner = cur.fetchone()[0].splitlines()[0]
        cur.execute(f"SELECT count(*) FROM {TABLE}")  # noqa: S608 — TABLE is internal config
        rows = cur.fetchone()[0]
    print(f"→ {banner}")
    print(f"→ {TABLE}: {rows} rows · VECTOR(1024, FLOAT32)")
    print()


async def main() -> None:
    preflight()
    prompt = (
        "Brief me on HNSW. Use my research corpus, cite the top three papers, "
        "then email a 2-sentence summary to me@org.com."
    )
    thread_id = f"demo-{uuid.uuid4().hex[:8]}"

    async for event in agent.run(prompt, thread_id=thread_id):
        match event:
            case ThinkEvent(iteration=i, reasoning=r, tool_calls=calls):
                if r:
                    print(f"\n💭 [iter {i}] thinking: {r.strip()}")
                if calls:
                    print(f"   plan → {', '.join(c.name for c in calls)}")
            case ToolStartEvent(tool_name="email_report", arguments=a):
                print(f"🔧 email_report(to={a.get('to')!r}, subject={a.get('subject')!r})")
                print(f"   ┌── EMAIL BODY ──────────────────────────────────────────")
                for line in textwrap.wrap(a.get("body", ""), width=70):
                    print(f"   │ {line}")
                print(f"   └────────────────────────────────────────────────────────")
            case ToolStartEvent(tool_name=n, arguments=a):
                args = ", ".join(f"{k}={v!r}" for k, v in a.items())[:80]
                print(f"🔧 {n}({args})")
            case ToolCompleteEvent(tool_name="search_corpus", result=r) if r:
                for row in json.loads(r):
                    print(f"   ↳ Oracle 26ai → id={row['id']:<10} score={row['score']:.3f}")
            case ToolCompleteEvent(tool_name="email_report", result=r) if r:
                d = json.loads(r)
                print(f"   ↳ email {d['via']} → {d['to']!r} ({d['chars']} chars)")
            case ReflectEvent(assessment=a, new_confidence=c):
                print(f"↻ reflexion: {a} (confidence {c:.2f})")
            case TerminateEvent(final_message=m):
                print(f"\n✓ {m}")


if __name__ == "__main__":
    asyncio.run(main())
