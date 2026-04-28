"""One-shot ingest of the Tokyo trip corpus into Oracle 26ai.

Two themes interleaved: food picks and culture picks. The cosine
distance over Cohere embeddings naturally separates them at search
time — each specialist gets its own query.
"""

from __future__ import annotations

import asyncio
import os

from locus.rag import OCIEmbeddings, OracleVectorStore, RAGRetriever


CORPUS = [
    # Food
    (
        "afuri-shinjuku",
        "Afuri Shinjuku — late-night yuzu shio ramen in Shinjuku. Light, "
        "citrusy broth; vegetarian option. Open until 4am, queues short "
        "after midnight.",
    ),
    (
        "tomoe-sushi",
        "Tomoe Sushi — Edomae omakase in Hatchobori. Fifteen courses, "
        "counter-only. Books out four weeks ahead; the hardest "
        "reservation in this corpus.",
    ),
    (
        "donjaca-izakaya",
        "Donjaca — standing izakaya in Shinbashi. No English menu, no "
        "tourists. Famous for their potato salad. Quick stop, one drink, "
        "move on.",
    ),
    (
        "uoshin-nogizaka",
        "Uoshin Nogizaka — fish izakaya, sashimi delivered direct from "
        "Tsukiji. Friendly to walk-ins. Good night-one warm-up.",
    ),
    # Culture
    (
        "jbs-shibuya",
        "JBS Shibuya — jazz listening bar tucked above a Family Mart. "
        "Owner-curated vinyl, 9 pm onward, conversation discouraged. The "
        "right cooldown after omakase.",
    ),
    (
        "blue-note-tokyo",
        "Blue Note Tokyo — flagship jazz club in Roppongi. Two sets "
        "nightly; book the second for a late-evening cap.",
    ),
    (
        "morioka-shoten",
        "Morioka Shoten — one-book-a-week shop in Ginza. The proprietor "
        "picks a single title and runs it for seven days. Obscure, "
        "perfect for the brief.",
    ),
    (
        "jimbocho-passage",
        "Jimbocho used-book passage — three blocks of secondhand "
        "stores. You can lose an entire afternoon. Strong on fine art "
        "monographs and out-of-print Japanese fiction.",
    ),
]


async def main() -> None:
    profile = os.environ.get("OCI_PROFILE", "DEFAULT")
    pw = os.environ["ORACLE_PASSWORD"]
    wallet = os.environ.get("ORACLE_WALLET", os.path.expanduser("~/.oci/wallets/deepresearch"))
    compartment = os.environ.get(
        "OCI_COMPARTMENT",
        "ocid1.tenancy.oc1..aaaaaaaaqlhpnytg33ztkwrdpq62p5yxx5gn5ltmkah23m7qebwjzc7x3lcq",
    )

    embedder = OCIEmbeddings(
        model_id="cohere.embed-english-v3.0",
        profile_name=profile,
        compartment_id=compartment,
        service_endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
    )
    store = OracleVectorStore(
        dsn=os.environ.get("ORACLE_DSN", "deepresearch_low"),
        user="ADMIN",
        password=pw,
        wallet_location=wallet,
        wallet_password=pw,
        dimension=1024,
        table_name="TOKYO_TRIP_RECS",
    )
    retriever = RAGRetriever(embedder=embedder, store=store)

    already = await retriever.retrieve("ramen", limit=1)
    if already.documents:
        print(f"TOKYO_TRIP_RECS already populated. {len(CORPUS)} expected.")
        return

    print(f"Ingesting {len(CORPUS)} Tokyo recommendations into Oracle 26ai…")
    for doc_id, content in CORPUS:
        await retriever.add_document(content, doc_id=doc_id, chunk=False)
        print(f"  + {doc_id}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
