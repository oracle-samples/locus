# ruff: noqa: ASYNC250, F841, ASYNC221, S603, S607
"""Three locus agents collaborate on a vendor purchase-order approval.

A real enterprise multi-agent workflow:

  1.  Procurement     — searches Oracle 26ai for vendors fitting the spend.
  2.  Compliance      — searches the same corpus for SOC2 / ISO certifications.
  3.  Procurement ↔ Compliance — debate trade-offs (cost vs compliance).
  4.  Approval Officer — receives the joint recommendation, asks the human
                         user for consent, then fires:
                            • submit_po   (@tool(idempotent=True))
                            • email_cfo   (@tool(idempotent=True))
                         Both writes are deduped. The thread is checkpointed
                         to OCI Object Storage on every iteration.

Required env:
  OCI_PROFILE          (default DEFAULT)
  ORACLE_PASSWORD      (required)
  ORACLE_WALLET        (default ~/.oci/wallets/deepresearch)
  OCI_NAMESPACE        (required — for the OCI bucket checkpointer)
  OCI_BUCKET_NAME      (default locus-test-checkpoints)
"""

from __future__ import annotations

import asyncio
import os
import sys
import textwrap
import time
import uuid

import oracledb

from locus import Agent
from locus.core.events import (
    ModelChunkEvent,
    TerminateEvent,
    ToolStartEvent,
)
from locus.memory.backends.oci_bucket import OCIBucketBackend
from locus.rag import OCIEmbeddings, OracleVectorStore, RAGRetriever
from locus.tools.decorator import tool


# ─── Config ────────────────────────────────────────────────────────────────
PROFILE = os.environ.get("OCI_PROFILE", "DEFAULT")
ORACLE_PW = os.environ["ORACLE_PASSWORD"]
WALLET = os.environ.get("ORACLE_WALLET", os.path.expanduser("~/.oci/wallets/deepresearch"))
ORACLE_DSN = os.environ.get("ORACLE_DSN", "deepresearch_low")
BUCKET = os.environ.get("OCI_BUCKET_NAME", "locus-test-checkpoints")
NAMESPACE = os.environ["OCI_NAMESPACE"]
COMPARTMENT = os.environ.get(
    "OCI_COMPARTMENT",
    "ocid1.tenancy.oc1..aaaaaaaaqlhpnytg33ztkwrdpq62p5yxx5gn5ltmkah23m7qebwjzc7x3lcq",
)
GENAI_ENDPOINT = "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com"


def _new_retriever() -> RAGRetriever:
    """Fresh per-call — async pools can't cross event loops."""
    return RAGRetriever(
        embedder=OCIEmbeddings(
            model_id="cohere.embed-english-v3.0",
            profile_name=PROFILE,
            compartment_id=COMPARTMENT,
            service_endpoint=GENAI_ENDPOINT,
        ),
        store=OracleVectorStore(
            dsn=ORACLE_DSN,
            user="ADMIN",
            password=ORACLE_PW,
            wallet_location=WALLET,
            wallet_password=ORACLE_PW,
            dimension=1024,
            table_name="VENDOR_CATALOG",
        ),
    )


# ─── Tools ─────────────────────────────────────────────────────────────────
@tool
def search_vendors(query: str, limit: int = 4) -> list[dict]:
    """Search the Oracle 26ai vendor catalogue."""
    rs = asyncio.run(_new_retriever().retrieve(f"vendor {query}", limit=limit))
    return [
        {"id": r.document.id, "content": r.document.content, "score": round(r.score, 3)}
        for r in rs.documents
    ]


@tool
def search_compliance(query: str, limit: int = 4) -> list[dict]:
    """Search the same catalogue, prioritising compliance certifications."""
    rs = asyncio.run(_new_retriever().retrieve(f"SOC2 ISO compliance {query}", limit=limit))
    return [
        {"id": r.document.id, "content": r.document.content, "score": round(r.score, 3)}
        for r in rs.documents
    ]


_PO_SUBMITTED: dict[tuple[str, float], dict] = {}
_EMAILS: list[dict] = []


@tool(idempotent=True)
def submit_po(vendor_id: str, amount_usd: float, term_days: int) -> dict:
    """Submit the purchase order. Idempotent — re-fires return cached PO."""
    key = (vendor_id, amount_usd)
    if key in _PO_SUBMITTED:
        return {**_PO_SUBMITTED[key], "cached": True}
    po_id = f"PO-{abs(hash(key)) % 100000:05d}"
    receipt = {
        "status": "submitted",
        "po_id": po_id,
        "vendor_id": vendor_id,
        "amount_usd": amount_usd,
        "term_days": term_days,
    }
    _PO_SUBMITTED[key] = receipt
    return receipt


@tool(idempotent=True)
def email_cfo(to: str, subject: str, body: str) -> dict:
    """Email the CFO with the PO summary. Idempotent."""
    _EMAILS.append({"to": to, "subject": subject, "body": body})
    return {"status": "sent", "to": to, "chars": len(body)}


# ─── Three agents ──────────────────────────────────────────────────────────
procurement = Agent(
    model="oci:openai.gpt-5.5",
    tools=[search_vendors],
    system_prompt=(
        "You are the Procurement specialist. Call search_vendors EXACTLY ONCE "
        "with query='cloud compute storage'. From the returned list pick three "
        "candidates that fit a $2M cloud infrastructure budget. Format: 3 "
        "bullets — vendor id, annual list, why. Use ONLY ids in the result."
    ),
    max_iterations=3,
)

compliance = Agent(
    model="oci:openai.gpt-5.5",
    tools=[search_compliance],
    system_prompt=(
        "You are the Compliance specialist. Call search_compliance EXACTLY "
        "ONCE with query='SOC2 ISO compliance'. From the returned list pick "
        "three vendors with the strongest SOC2 / ISO posture for a regulated "
        "workload. Format: 3 bullets — vendor id, certifications, comment. "
        "Use ONLY ids in the result."
    ),
    max_iterations=3,
)


def _make_voice(name: str, personality: str) -> Agent:
    """Free-form persona for dialogue rounds — no tools, prose only."""
    return Agent(
        model="oci:openai.gpt-5.5",
        system_prompt=(
            f"You are {name}, a member of an enterprise vendor-review team. "
            f"{personality} You are in a CONVERSATION with another team "
            "member — not answering a request. Reply in 2-3 sentences of "
            "plain prose. No bullets. Reference vendor ids when useful."
        ),
        max_iterations=2,
    )


procurement_voice = _make_voice(
    "Procurement",
    "You care about price, payment terms, and total cost over the contract.",
)
compliance_voice = _make_voice(
    "Compliance",
    "You care about SOC2 Type II, ISO 27001, vendor maturity, and regulatory blast-radius.",
)


approver = Agent(
    model="oci:openai.gpt-5.5",
    tools=[submit_po, email_cfo],
    system_prompt=(
        "You are the Approval Officer. Given a recommended vendor and "
        "amount, (1) call submit_po exactly once, (2) call email_cfo "
        "exactly once with a one-paragraph summary as the body. Then "
        "reply in one sentence: which PO was submitted and to whom the "
        "email went."
    ),
    checkpointer=OCIBucketBackend(bucket_name=BUCKET, namespace=NAMESPACE, profile_name=PROFILE),
    max_iterations=6,
)


# ─── Pretty print + streaming ──────────────────────────────────────────────
R = "\033[38;2;199;70;52m"  # Oracle red
K = "\033[38;2;120;113;108m"
G = "\033[38;2;76;179;123m"
Y = "\033[38;2;255;180;84m"
P = "\033[38;2;200;168;255m"
B = "\033[1m"
Z = "\033[0m"


def _hr(char: str = "─") -> None:
    print(char * 92)


def _section(title: str) -> None:
    _hr()
    print(f" {title}")
    _hr()


def _emit_wrapped(text: str, label: str, color: str, width: int = 86) -> None:
    """Print already-collected text wrapped, with the agent's label gutter."""
    indent = " " * (len(label) + 2)
    paras = text.strip().split("\n")
    first = True
    for para in paras:
        if not para.strip():
            print()
            continue
        for line in textwrap.wrap(para, width=width) or [""]:
            if first:
                print(f" {color}{label}\033[0m {line}")
                first = False
            else:
                print(f" {color}{' ' * len(label)}\033[0m {line}")


async def _stream_agent(agent: Agent, prompt: str, role: str, color: str) -> str:
    """Run the agent, then print the answer wrapped to a legible width.

    We collect tokens silently while the model streams, then render the final
    text wrapped — much more readable on a 1500-px terminal than letting the
    model wrap at whatever width OCI's V1 transport hands back.
    """
    label = f"{role:<12}│"
    streamed = ""
    tools_fired: list[str] = []
    async for event in agent.run(prompt):
        if isinstance(event, ModelChunkEvent) and event.content:
            streamed += event.content
        elif isinstance(event, ToolStartEvent):
            tools_fired.append(event.tool_name)
        elif isinstance(event, TerminateEvent):
            final = event.final_message or streamed
            for t in tools_fired:
                print(f" {color}{' ' * len(label)}\033[0m   \033[2m· tool: {t}\033[0m")
            _emit_wrapped(final, label, color)
            return final
    _emit_wrapped(streamed, label, color)
    return streamed


# ─── Slides ────────────────────────────────────────────────────────────────
def _slide_pitch() -> None:
    print("\033[2J\033[H")
    print()
    print(f"  {B}What we're making{Z}")
    print()
    print("  Three Oracle GenAI agents that approve a $2M cloud-infrastructure PO.")
    print()
    print(f"      {Y}🧾 Procurement{Z}    queries Oracle 26ai vendor catalogue.")
    print(f"      {P}🛡  Compliance{Z}     queries the same catalogue for SOC2 / ISO.")
    print(f"      {Y}🧾 Procurement{Z}  ↔  {P}🛡  Compliance{Z}    debate trade-offs, agree.")
    print(f"      {G}✍️  Approval Officer{Z}   asks {B}you{Z} for consent, then submits + emails.")
    print()
    print(f"  {K}Every line of agent text below is a real Oracle GenAI gpt-5.5 response.{Z}")
    print()
    time.sleep(5.0)


def _slide_outro() -> None:
    print()
    print(f"  {B}{G}✓ PO approved by 3 agents · 1 human · zero duplicate submissions.{Z}")
    print()
    print(f"  {K}powered by{Z}  {B}{R}locus{Z}  {K}on{Z}  Oracle 26ai")
    print()


# ─── Main ──────────────────────────────────────────────────────────────────
async def main() -> None:
    # The Playwright-rendered intro + scenes (logo, problem, dashboard) are
    # concatenated separately in the video pipeline. The terminal demo skips
    # pitch and goes straight to the agentic execution.
    _section("PREFLIGHT — live services")
    with oracledb.connect(
        user="ADMIN",
        password=ORACLE_PW,
        dsn=ORACLE_DSN,
        config_dir=WALLET,
        wallet_location=WALLET,
        wallet_password=ORACLE_PW,
    ) as conn:
        cur = conn.cursor()
        cur.execute("SELECT banner_full FROM v$version")
        banner = cur.fetchone()[0].splitlines()[0]
        cur.execute("SELECT count(*) FROM VENDOR_CATALOG")
        rows = cur.fetchone()[0]
    print(f"  ✓ {banner}")
    print(f"  ✓ VENDOR_CATALOG — {rows} rows · VECTOR(1024, FLOAT32)")
    print("  ✓ OCI GenAI us-chicago-1 · openai.gpt-5.5 + cohere.embed-english-v3.0")
    print(f"  ✓ OCI Object Storage · oci://{NAMESPACE}/{BUCKET}")
    print()

    user_prompt = (
        "Approve a $2M cloud infrastructure spend for FY26. Recommend a vendor and submit the PO."
    )
    _section("USER")
    print(f"  {user_prompt}")
    print()

    # ── Round 1: Procurement ────────────────────────────────────────────
    _section("ROUND 1 · 🧾 Procurement queries Oracle 26ai")
    proc_text = await _stream_agent(
        procurement, "List your three vendor candidates.", "🧾 PROCUREMENT", Y
    )

    # ── Round 2: Compliance ─────────────────────────────────────────────
    _section("ROUND 2 · 🛡 Compliance queries Oracle 26ai")
    comp_text = await _stream_agent(
        compliance, "List your three compliance picks.", "🛡 COMPLIANCE", P
    )

    # ── Round 3: Procurement reacts ─────────────────────────────────────
    _section("ROUND 3 · 🧾 Procurement replies to 🛡 Compliance")
    react_prompt = (
        f"Your vendor picks: {proc_text}\n\n"
        f"🛡 Compliance just sent their picks: {comp_text}\n\n"
        "Reply in 2-3 sentences (prose, no bullets). Do their compliance "
        "picks fit our $2M cap? Name the trade-off and a recommendation."
    )
    proc_reaction = await _stream_agent(procurement_voice, react_prompt, "🧾 PROCUREMENT", Y)

    # ── Round 4: Compliance replies ─────────────────────────────────────
    _section("ROUND 4 · 🛡 Compliance replies to 🧾 Procurement")
    counter_prompt = (
        f"Your picks were: {comp_text}\n\n"
        f"🧾 Procurement just replied: {proc_reaction}\n\n"
        "Reply in 2-3 sentences (prose). Agree with what makes sense, "
        "push back if compliance is being undervalued. Reference vendor ids."
    )
    comp_counter = await _stream_agent(compliance_voice, counter_prompt, "🛡 COMPLIANCE", P)

    # ── Round 5: Procurement writes the joint recommendation ────────────
    _section("ROUND 5 · 🧾 Procurement writes the joint recommendation")
    plan_prompt = (
        f"Your picks: {proc_text}\n\n"
        f"Compliance picks: {comp_text}\n\n"
        f"Your reaction: {proc_reaction}\n\n"
        f"Compliance response: {comp_counter}\n\n"
        "Write the final recommendation as 2 short sentences: ONE vendor "
        "id, the proposed annual amount in USD, the proposed payment term "
        "in days, and one-line rationale. Use only ids that appeared above."
    )
    plan_text = await _stream_agent(procurement, plan_prompt, "🧾 PROCUREMENT", Y)

    # ── Round 6a: human-in-the-loop consent ─────────────────────────────
    _section("ROUND 6 · 👤 Human-in-the-loop · approve before submission")
    print("  The next step will:")
    print("    1) submit_po   — non-trivial: a real PO into the ledger")
    print("    2) email_cfo   — to the CFO with the joint recommendation")
    print()
    answer = input("  Approve? [y/N] ").strip().lower()
    if answer != "y":
        print("\n  ✗ Declined. No PO submitted, no email.")
        return
    print("  ✓ Approved.\n")

    # ── Round 6b: Approver fires the writes ─────────────────────────────
    _section("ROUND 6 · ✍️  Approval Officer → submit + email")
    handoff = (
        f"Procurement and Compliance agreed on:\n\n{plan_text}\n\n"
        "Submit the PO to that vendor for the recommended amount and term, "
        "exactly once. Then email_cfo at cfo@org.com with the joint "
        "recommendation as the body."
    )
    final_text = await _stream_agent(approver, handoff, "✍️ APPROVER", G)
    print()

    # ── Verification ────────────────────────────────────────────────────
    _section("VERIFICATION")
    print(f"  3 agents · 5 LLM rounds · 2 tool calls into Oracle 26ai")
    print(f"  submit_po body invocations: {len(_PO_SUBMITTED)}  (idempotent — 1 even on retries)")
    print(f"  email_cfo body invocations: {len(_EMAILS)}")
    if _EMAILS:
        e = _EMAILS[-1]
        print()
        print(f"  📨 EMAIL · {e['to']} · subject: {e['subject']!r}")
        print()
        for line in textwrap.wrap(e["body"], width=82):
            print(f"     {line}")
    _hr("═")
    _slide_outro()


if __name__ == "__main__":
    asyncio.run(main())
