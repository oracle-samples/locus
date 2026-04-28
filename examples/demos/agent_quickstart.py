# Locus — three tools, idempotent write, real ReAct loop.
#
# • @tool — Pydantic-validated, JSON schema auto-generated.
# • @tool(idempotent=True) — write-side dedup, no double-sends.
# • Agent(model="oci:...") — OCI GenAI V1, profile from OCI_PROFILE.

from locus import Agent, tool


PAPERS = [
    ("Faiss: Efficient Similarity Search", 2017, 8400),
    ("HNSW: Hierarchical Navigable Small World", 2018, 4500),
    ("Pinecone whitepaper", 2022, 1200),
]


@tool
def search_papers(topic: str) -> list[dict]:
    """Search the literature for a topic."""
    if any(k in topic.lower() for k in ("vector", "similarity", "ann")):
        return [{"title": t, "year": y, "citations": c} for t, y, c in PAPERS]
    return []


@tool
def rank_by_citations(papers: list[dict]) -> dict:
    """Pick the most-cited paper from the list."""
    return max(papers, key=lambda p: p["citations"])


@tool(idempotent=True)
def email_report(to: str, subject: str, body: str) -> dict:
    """Send the report. Idempotent — re-fires return cached results."""
    return {"status": "sent", "to": to, "chars": len(body)}


agent = Agent(
    model="oci:openai.gpt-5.5",
    tools=[search_papers, rank_by_citations, email_report],
    system_prompt="Search → rank → email exactly once. One-sentence reply.",
)

r = agent.run_sync(
    "Find vector-DB papers, pick the most-cited, and email a 2-sentence summary to me@org.com."
)

print(f"\n{r.message}\n")
for t in r.tool_executions:
    print(f"  → {t.tool_name}({list(t.arguments.keys())})")
print(f"\niterations: {r.metrics.iterations}   tools: {len(r.tool_executions)}")
