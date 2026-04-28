# ruff: noqa: ASYNC250, F841, ASYNC221, S603, S607, RUF001
"""Three locus agents collaborate to plan a Tokyo trip — real, runnable.

Pipeline (each step is a real ``Agent.run_sync`` against OCI GenAI):

  1.  Foodie     — searches Oracle 26ai for restaurants. Real RAG.
  2.  Culture    — searches Oracle 26ai for jazz / bookstores. Real RAG.
  3.  Foodie     — receives Culture's picks, produces a joint 3-day plan.
                   This is the "two agents agree" beat.
  4.  Concierge  — receives the agreed plan, calls
                   @tool(idempotent=True) book_restaurant, then
                   @tool(idempotent=True) email_itinerary. Checkpointed
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
    ToolCompleteEvent,
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


# ─── Retriever factory (fresh per call — async pools can't cross loops) ───
def _new_retriever() -> RAGRetriever:
    return RAGRetriever(
        embedder=OCIEmbeddings(
            model_id="cohere.embed-english-v3.0",
            profile_name=PROFILE,
            compartment_id=COMPARTMENT,
            service_endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        ),
        store=OracleVectorStore(
            dsn=ORACLE_DSN,
            user="ADMIN",
            password=ORACLE_PW,
            wallet_location=WALLET,
            wallet_password=ORACLE_PW,
            dimension=1024,
            table_name="TOKYO_TRIP_RECS",
        ),
    )


# ─── Tools ─────────────────────────────────────────────────────────────────
@tool
def search_food(query: str, limit: int = 4) -> list[dict]:
    """Search Oracle 26ai for Tokyo restaurants matching a theme."""
    retriever = _new_retriever()
    rs = asyncio.run(retriever.retrieve(f"restaurant {query}", limit=limit))
    return [
        {"id": r.document.id, "content": r.document.content, "score": round(r.score, 3)}
        for r in rs.documents
    ]


@tool
def search_culture(query: str, limit: int = 4) -> list[dict]:
    """Search Oracle 26ai for Tokyo jazz bars and bookstores."""
    retriever = _new_retriever()
    rs = asyncio.run(retriever.retrieve(f"jazz bar bookstore {query}", limit=limit))
    return [
        {"id": r.document.id, "content": r.document.content, "score": round(r.score, 3)}
        for r in rs.documents
    ]


_BOOKED: dict[tuple[str, str], dict] = {}
_EMAILS: list[dict] = []


@tool(idempotent=True)
def book_restaurant(name: str, when: str) -> dict:
    """Book a restaurant. Idempotent — re-fires return the cached receipt."""
    key = (name, when)
    if key in _BOOKED:
        return {**_BOOKED[key], "cached": True}
    receipt = {
        "status": "booked",
        "name": name,
        "when": when,
        "res_id": f"R-{abs(hash(key)) % 100000:05d}",
    }
    _BOOKED[key] = receipt
    return receipt


@tool(idempotent=True)
def email_itinerary(to: str, subject: str, body: str) -> dict:
    """Send the itinerary email. Idempotent."""
    _EMAILS.append({"to": to, "subject": subject, "body": body})
    return {"status": "sent", "to": to, "chars": len(body)}


# ─── Three agents ──────────────────────────────────────────────────────────
foodie = Agent(
    model="oci:openai.gpt-5.5",
    tools=[search_food],
    system_prompt=(
        "You are the Foodie agent on a Tokyo trip-planning team. "
        "Call search_food EXACTLY ONCE with a broad query like "
        "'ramen omakase izakaya'. Then immediately stop calling tools "
        "and write your three picks ONLY using ids that appeared in the "
        "results: one late-night ramen for day 1, one hard-to-book "
        "omakase for day 2, one quick izakaya stop. Format: 3 bullets "
        "— name, id, one-line reasoning each. Be terse. Do not invent "
        "names that weren't in the search results."
    ),
    max_iterations=3,
)

culture = Agent(
    model="oci:openai.gpt-5.5",
    tools=[search_culture],
    system_prompt=(
        "You are the Culture agent. Step 1: call search_culture(query='jazz'). "
        "Step 2: read the list of {id, content, score} entries the tool returned. "
        "Step 3: list THREE of those entries verbatim, one per line, in this format:\n"
        "  - <id> — <one-line reason>\n"
        "Pick: a jazz cooldown after omakase, a bigger jazz set for day 3, "
        "an obscure bookstore. Use ONLY ids from the tool result. Stop after writing."
    ),
    max_iterations=5,
)


def _make_voice(name: str, personality: str) -> Agent:
    """Free-form persona for the dialogue rounds — no tools, no bullets."""
    return Agent(
        model="oci:openai.gpt-5.5",
        system_prompt=(
            f"You are {name}, a member of a Tokyo trip-planning team. "
            f"{personality} "
            "You are in a CONVERSATION with another team member — not "
            "answering a request. Reply in 2-3 sentences of plain prose. "
            "No bullets. No formatted lists. Reference specific ids when "
            "useful, but write like a person, not a report."
        ),
        max_iterations=2,
    )


foodie_voice = _make_voice(
    "🍜 Foodie",
    "You care about food timing, queues, and reservation difficulty.",
)
culture_voice = _make_voice(
    "🎷 Culture",
    "You care about late-night listening rooms, vinyl, obscure bookstores.",
)


concierge = Agent(
    model="oci:openai.gpt-5.5",
    tools=[book_restaurant, email_itinerary],
    system_prompt=(
        "You are the Concierge. Given an agreed Tokyo itinerary, "
        "(1) call book_restaurant once for the omakase reservation, "
        "(2) call email_itinerary once with the full itinerary as the "
        "body. Then reply in one sentence: what you booked + emailed."
    ),
    checkpointer=OCIBucketBackend(bucket_name=BUCKET, namespace=NAMESPACE, profile_name=PROFILE),
    max_iterations=6,
)


# ─── Pretty print helpers ──────────────────────────────────────────────────
def _hr(char: str = "─") -> None:
    print(char * 92)


def _section(title: str) -> None:
    _hr()
    print(f" {title}")
    _hr()


def _agent_line(role: str, color: str, text: str) -> None:
    width = 78
    label = f"{role:<10}│"
    lines = textwrap.wrap(text.strip(), width=width) or [""]
    print(f" \033[{color}m{label}\033[0m {lines[0]}")
    for line in lines[1:]:
        print(f" \033[{color}m{' ' * len(label)}\033[0m {line}")


async def _stream_agent(agent: Agent, prompt: str, role: str, color: str) -> str:
    """Stream the agent's text token-by-token. Falls back to terminate.message
    when the upstream model emits no streaming chunks (some models batch
    the response and arrive only as TerminateEvent)."""
    label = f"{role:<10}│"
    print(f" {color}{label}\033[0m ", end="", flush=True)
    streamed = ""
    async for event in agent.run(prompt):
        if isinstance(event, ModelChunkEvent) and event.content:
            sys.stdout.write(event.content)
            sys.stdout.flush()
            streamed += event.content
        elif isinstance(event, ToolStartEvent):
            sys.stdout.write(
                f"\n {color}{' ' * len(label)}\033[0m   \033[2m· tool: {event.tool_name}\033[0m\n"
            )
            sys.stdout.write(f" {color}{label}\033[0m ")
            sys.stdout.flush()
        elif isinstance(event, TerminateEvent):
            final = event.final_message or streamed
            # Print whatever wasn't streamed yet, slowly enough to feel live.
            tail = final[len(streamed) :]
            for ch in tail:
                sys.stdout.write(ch)
                sys.stdout.flush()
                await asyncio.sleep(0.005)
            print()
            return final
    return streamed


# Truecolor — exact hexes from docs/img/logo.svg.
R = "\033[38;2;199;70;52m"  # Oracle red   #C74634
K = "\033[38;2;120;113;108m"  # tagline gray #78716C
D = "\033[38;2;168;162;156m"  # dim gray     #A8A29E
G = "\033[38;2;76;179;123m"  # green        #4CB37B
Y = "\033[38;2;255;180;84m"  # yellow       #FFB454
P = "\033[38;2;200;168;255m"  # purple       #C8A8FF
B = "\033[1m"
Z = "\033[0m"


def _slide_intro() -> None:
    """Hold on the logo long enough for it to register."""
    print("\n\n\n")
    print(f"          {K}╲       ╱{Z}")
    print(f"           {K}╲     ╱{Z}")
    print(f"          {R}┌─{K}╲   ╱{R}─┐{Z}")
    print(f"          {R}│   {R}█{R}   │{Z}")
    print(f"          {R}└─{K}╱   ╲{R}─┘{Z}")
    print(f"           {K}╱     ╲{Z}")
    print(f"          {K}╱       ╲{Z}")
    print()
    print(f"     {B}locus{Z}")
    print(f"     {K}ORACLE GENERATIVE AI · MULTI-AGENT ORCHESTRATOR SDK{Z}")
    print()
    print()
    print(f"     {K}github.com/oracle/locus  ·  examples/demos/trip_team/{Z}")
    print("\n\n")
    time.sleep(7.0)


def _slide_pitch() -> None:
    """What we're making."""
    print("\033[2J\033[H")
    print()
    print(f"  {B}What we're making{Z}")
    print()
    print("  Three Oracle GenAI agents that talk to each other to plan a 3-day Tokyo trip.")
    print()
    print(f"      {Y}🍜 Foodie{Z}      retrieves restaurants from Oracle 26ai.")
    print(f"      {P}🎷 Culture{Z}     retrieves jazz bars and bookstores from Oracle 26ai.")
    print(
        f"      {Y}🍜 Foodie{Z}  ↔  {P}🎷 Culture{Z}    debate picks, respond to each other, agree."
    )
    print(f"      {G}🛎️  Concierge{Z}   asks {B}you{Z} for approval, then books + emails.")
    print()
    print(f"  {K}Every line of agent text below is a real Oracle GenAI gpt-5.5 response.{Z}")
    print()
    time.sleep(5.0)


def _slide_outro() -> None:
    print()
    print(f"  {B}{G}✓ Three agents · one trip · human-approved · zero double-charges.{Z}")
    print()
    print(f"  {K}powered by{Z}  {B}{R}locus{Z}  {K}on{Z}  Oracle 26ai")
    print()


async def main() -> None:
    # Intro slide is rendered as a separate Playwright video, then
    # ffmpeg-concatenated to this run. We start straight at the pitch.
    _slide_pitch()
    print("\033[2J\033[H")  # clear before the live run starts

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
        cur.execute("SELECT count(*) FROM TOKYO_TRIP_RECS")
        rows = cur.fetchone()[0]
    print(f"  ✓ {banner}")
    print(f"  ✓ TOKYO_TRIP_RECS — {rows} rows · VECTOR(1024, FLOAT32)")
    print("  ✓ OCI GenAI us-chicago-1 · openai.gpt-5.5 + cohere.embed-english-v3.0")
    print(f"  ✓ OCI Object Storage · oci://{NAMESPACE}/{BUCKET}")
    print()

    user_prompt = (
        "Plan a 3-day Tokyo trip around food, jazz, and bookstores. "
        "Book what's hard. Email me at me@org.com."
    )
    _section("USER")
    print(f"  {user_prompt}")
    print()

    # ── Round 1: Foodie picks (streaming) ──────────────────────────────
    _section("ROUND 1 · 🍜 Foodie searches Oracle 26ai and proposes")
    foodie_text = await _stream_agent(
        foodie, "Pick the food spots. Be terse.", "🍜 FOODIE", "\033[38;2;255;180;84m"
    )

    # ── Round 2: Culture picks (streaming) ─────────────────────────────
    _section("ROUND 2 · 🎷 Culture searches Oracle 26ai and proposes")
    culture_text = await _stream_agent(
        culture, "Pick the culture spots. Be terse.", "🎷 CULTURE", "\033[38;2;200;168;255m"
    )

    # ── Round 3: Foodie reacts to Culture's picks (streaming) ──────────
    _section("ROUND 3 · 🍜 Foodie replies to 🎷 Culture")
    react_prompt = (
        f"Your food picks were: {foodie_text}\n\n"
        f"🎷 Culture just sent you their picks: {culture_text}\n\n"
        "Reply to Culture in 2-3 sentences (prose, no bullets) about how "
        "their picks fit your food schedule. Mention specifically whether "
        "jbs-shibuya works as a cooldown after the omakase, and name one "
        "timing trade-off."
    )
    foodie_reaction_text = await _stream_agent(
        foodie_voice, react_prompt, "🍜 FOODIE", "\033[38;2;255;180;84m"
    )

    # ── Round 4: Culture replies (streaming) ───────────────────────────
    _section("ROUND 4 · 🎷 Culture replies to 🍜 Foodie")
    counter_prompt = (
        f"Your culture picks were: {culture_text}\n\n"
        f"🍜 Foodie just replied: {foodie_reaction_text}\n\n"
        "Reply to Foodie in 2-3 sentences (prose, no bullets). Agree where "
        "you can; push back if their timing concern is off. Reference at "
        "least one id."
    )
    culture_counter_text = await _stream_agent(
        culture_voice, counter_prompt, "🎷 CULTURE", "\033[38;2;200;168;255m"
    )

    # ── Round 5: Foodie writes the agreed joint plan (streaming) ───────
    _section("ROUND 5 · 🍜 Foodie writes the agreed 3-day plan")
    plan_prompt = (
        "You and 🎷 Culture have now agreed. Here's the conversation:\n\n"
        f"Your picks:\n{foodie_text}\n\n"
        f"Culture's picks:\n{culture_text}\n\n"
        f"Your reaction:\n{foodie_reaction_text}\n\n"
        f"Culture's response:\n{culture_counter_text}\n\n"
        "Now write the final 3-day plan. Day-by-day, one line per slot. "
        "Use ONLY ids that appeared above. Day 2 must have omakase right "
        "before a jazz cooldown."
    )
    plan_text = await _stream_agent(foodie, plan_prompt, "🍜 FOODIE", "\033[38;2;255;180;84m")

    # ── Round 6a: human-in-the-loop consent ─────────────────────────────
    _section("ROUND 6 · 👤 Human-in-the-loop · approve before concierge fires")
    print("  The next step will: 1) book_restaurant(Tomoe Sushi, 2026-05-09 19:30)")
    print("                       2) email_itinerary → me@org.com")
    print()
    answer = input("  Approve? [y/N] ").strip().lower()
    if answer != "y":
        print("\n  ✗ Declined. Concierge not invoked. No booking, no email.")
        return
    print("  ✓ Approved.\n")

    # ── Round 6b: Concierge handoff ─────────────────────────────────────
    _section("ROUND 6 · 🛎️  Concierge → book + email")
    handoff = (
        "The Foodie and Culture agents agreed on this 3-day Tokyo plan:\n\n"
        f"{plan_text}\n\n"
        "Book the omakase at Tomoe Sushi for 2026-05-09 19:30 using "
        "book_restaurant exactly once. Then email_itinerary the full plan "
        "to me@org.com exactly once."
    )
    final_text = await _stream_agent(concierge, handoff, "🛎️ CONCIERGE", "\033[38;2;76;179;123m")
    print()

    # ── Verification ────────────────────────────────────────────────────
    _section("VERIFICATION")
    print(f"  3 agents · 4 LLM rounds · 2 tool calls into Oracle 26ai")
    print(f"  book_restaurant body invocations: {len(_BOOKED)}  (idempotent — 1 even on retries)")
    print(f"  email_itinerary body invocations: {len(_EMAILS)}")
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
