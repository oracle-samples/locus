"""One-shot ingest of a vendor catalogue into Oracle 26ai.

Eight vendor entries with pricing, certifications and payment terms.
Idempotent — re-running is a no-op once VENDOR_CATALOG is populated.
"""

from __future__ import annotations

import asyncio
import os

from locus.rag import OCIEmbeddings, OracleVectorStore, RAGRetriever


CORPUS = [
    (
        "vendor-acme-cloud",
        "ACME Cloud Services. Compute + storage. Annual list $2.4M. "
        "SOC2 Type II + ISO 27001. Payment: NET-60. "
        "Used by 4 of the Fortune-500 banks. Strong incumbent.",
    ),
    (
        "vendor-techgrid-dc",
        "TechGrid Datacenter. Colo + bare-metal. Annual list $1.8M. "
        "SOC2 Type I only. Payment: NET-30. Solid mid-tier; "
        "smaller blast radius than ACME but no Type II yet.",
    ),
    (
        "vendor-bytewave",
        "ByteWave Storage. Object + cold-tier. Annual list $0.9M. "
        "ISO 27001 only, no SOC2. Payment: NET-45. "
        "Cheapest viable option but compliance gap on SOC2.",
    ),
    (
        "vendor-quantumstream",
        "QuantumStream Networks. SD-WAN + private interconnect. "
        "Annual list $3.1M. SOC2 + HIPAA + FedRAMP Moderate. "
        "Payment: NET-90. Premium tier; strict compliance.",
    ),
    (
        "vendor-edgecdn",
        "EdgeCDN Global. Edge delivery + DDoS. Annual list $0.62M. "
        "ISO 27001. Payment: NET-30. Niche; not a primary cloud "
        "provider, doesn't satisfy compute spend.",
    ),
    (
        "vendor-meridian",
        "Meridian Cloud. Compute + database. Annual list $2.1M. "
        "SOC2 Type II + HIPAA. Payment: NET-45. Comparable to "
        "ACME on compliance, ~12% cheaper, smaller market share.",
    ),
    (
        "vendor-cobalt-labs",
        "Cobalt Labs. AI-managed Kubernetes. Annual list $1.4M. "
        "SOC2 Type II. Payment: NET-30. Strong technical fit, "
        "but only 18 months old — vendor-risk concern.",
    ),
    (
        "vendor-orion-systems",
        "Orion Systems. Bare-metal + GPU. Annual list $2.8M. "
        "SOC2 + ISO 27001. Payment: NET-60. Heavy on GPU, light "
        "on storage. Good if AI workloads dominate.",
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
        table_name="VENDOR_CATALOG",
    )
    retriever = RAGRetriever(embedder=embedder, store=store)

    already = await retriever.retrieve("compute vendor", limit=1)
    if already.documents:
        print(f"VENDOR_CATALOG already populated. {len(CORPUS)} expected.")
        return

    print(f"Ingesting {len(CORPUS)} vendor entries into Oracle 26ai…")
    for doc_id, content in CORPUS:
        await retriever.add_document(content, doc_id=doc_id, chunk=False)
        print(f"  + {doc_id}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
