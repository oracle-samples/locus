# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 22: RAG Basics - Retrieval Augmented Generation

This tutorial introduces RAG (Retrieval Augmented Generation), which enables
your agents to access and use knowledge from your documents.

What you'll learn:
- What RAG is and why it's useful
- How embeddings work
- Using vector stores to store and search documents
- Building a complete RAG pipeline

Prerequisites:
- Set OPENAI_API_KEY environment variable, or
- Have OCI config with DEFAULT profile

Run:
    python examples/tutorial_22_rag_basics.py
"""

import asyncio
import os


# =============================================================================
# What is RAG?
# =============================================================================

"""
RAG (Retrieval Augmented Generation) allows LLMs to access external knowledge.

The flow is:
1. EMBED: Convert documents into vectors (embeddings)
2. STORE: Save vectors in a vector database
3. SEARCH: Find relevant documents using semantic similarity
4. GENERATE: Use retrieved context in LLM prompts

Why RAG?
- LLMs have knowledge cutoffs (they don't know recent events)
- LLMs can't access your private/proprietary data
- RAG grounds responses in your actual documents
- Reduces hallucinations by providing source material
"""


# =============================================================================
# Step 1: Understanding Embeddings
# =============================================================================


async def understand_embeddings():
    """
    Embeddings convert text into numerical vectors that capture meaning.

    Similar texts have similar vectors (high cosine similarity).
    Different texts have different vectors (low cosine similarity).
    """
    print("=" * 60)
    print("Tutorial 22: Understanding Embeddings")
    print("=" * 60)

    # Choose embedder based on available credentials
    embedder = get_embedder()
    print(f"Using embedder: {embedder.__class__.__name__}")
    print(f"Embedding dimension: {embedder.config.dimension}")

    # Embed some texts
    texts = [
        "Python is a programming language",
        "Python is used for machine learning",
        "Cats are fluffy animals",
    ]

    print("\nEmbedding texts...")
    results = await embedder.embed_batch(texts)

    # Show first few dimensions of each embedding
    for i, result in enumerate(results):
        preview = result.embedding[:5]
        print(f"\n'{texts[i]}'")
        print(f"  First 5 dims: {[round(x, 4) for x in preview]}")
        print(f"  Total dims: {len(result.embedding)}")

    # Calculate similarity
    import math

    def cosine_similarity(a, b):
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b)

    sim_01 = cosine_similarity(results[0].embedding, results[1].embedding)
    sim_02 = cosine_similarity(results[0].embedding, results[2].embedding)

    print("\n" + "-" * 40)
    print("Similarity Analysis:")
    print(f"  'Python programming' vs 'Python ML': {sim_01:.4f}")
    print(f"  'Python programming' vs 'Cats': {sim_02:.4f}")
    print("\nNote: Higher similarity = more semantically related")


# =============================================================================
# Step 2: Using Vector Stores
# =============================================================================


async def using_vector_stores():
    """
    Vector stores save embeddings and enable fast similarity search.

    Locus supports multiple vector stores:
    - InMemoryVectorStore: Great for prototyping
    - QdrantVectorStore: Production-ready, cloud or local
    - OpenSearchVectorStore: Enterprise search with vectors
    """
    print("\n" + "=" * 60)
    print("Tutorial 22: Using Vector Stores")
    print("=" * 60)

    from locus.rag.stores.base import Document
    from locus.rag.stores.memory import InMemoryVectorStore

    embedder = get_embedder()

    # Create in-memory store
    store = InMemoryVectorStore(dimension=embedder.config.dimension)
    print(f"Created store with dimension: {store.config.dimension}")

    # Prepare documents
    docs_text = [
        "Python is great for data science and machine learning.",
        "JavaScript is the language of the web browser.",
        "Oracle Database is an enterprise relational database.",
        "PostgreSQL is a popular open-source database.",
        "Docker containers package applications with dependencies.",
    ]

    # Embed and add documents
    print("\nAdding documents...")
    for i, text in enumerate(docs_text):
        result = await embedder.embed(text)
        doc = Document(
            id=f"doc_{i}",
            content=text,
            embedding=result.embedding,
            metadata={"source": "tutorial", "index": i},
        )
        await store.add(doc)
        print(f"  Added: {text[:40]}...")

    # Search
    print("\n" + "-" * 40)
    print("Searching for 'database systems'...")

    query_result = await embedder.embed("database systems")
    search_results = await store.search(
        query_embedding=query_result.embedding,
        limit=3,
    )

    print("\nTop 3 results:")
    for i, result in enumerate(search_results, 1):
        print(f"  {i}. Score: {result.score:.4f}")
        print(f"     {result.document.content}")

    # Count and clear
    count = await store.count()
    print(f"\nTotal documents in store: {count}")


# =============================================================================
# Step 3: The RAG Retriever
# =============================================================================


async def using_rag_retriever():
    """
    The RAGRetriever combines embeddings and storage into a simple API.

    It handles:
    - Automatic embedding of documents and queries
    - Document chunking for long texts
    - Metadata preservation
    - Convenient retrieval methods
    """
    print("\n" + "=" * 60)
    print("Tutorial 22: Using RAG Retriever")
    print("=" * 60)

    from locus.rag import RAGRetriever
    from locus.rag.stores.memory import InMemoryVectorStore

    embedder = get_embedder()
    store = InMemoryVectorStore(dimension=embedder.config.dimension)

    # Create retriever
    retriever = RAGRetriever(
        embedder=embedder,
        store=store,
        chunk_size=500,  # Split long docs into 500-char chunks
        chunk_overlap=50,  # Overlap between chunks
    )

    print("Created RAGRetriever")
    print("  Chunk size: 500 chars")
    print("  Chunk overlap: 50 chars")

    # Add documents (no need to embed manually!)
    knowledge_base = [
        """
        Python was created by Guido van Rossum and first released in 1991.
        It emphasizes code readability with its notable use of significant
        indentation. Python is dynamically typed and garbage-collected.
        It supports multiple programming paradigms, including structured,
        object-oriented, and functional programming.
        """,
        """
        Oracle Cloud Infrastructure (OCI) is a cloud computing service
        offered by Oracle Corporation. It provides servers, storage,
        network, applications and services through a global network of
        Oracle Corporation managed data centers. OCI offers infrastructure
        as a service (IaaS), platform as a service (PaaS), and software
        as a service (SaaS).
        """,
        """
        Machine learning is a subset of artificial intelligence (AI) that
        provides systems the ability to automatically learn and improve
        from experience without being explicitly programmed. Machine learning
        focuses on the development of computer programs that can access data
        and use it to learn for themselves.
        """,
    ]

    print("\nAdding knowledge base documents...")
    for doc in knowledge_base:
        ids = await retriever.add_document(doc.strip())
        print(f"  Added document with {len(ids)} chunks")

    # Retrieve with natural language query
    print("\n" + "-" * 40)
    print("Querying: 'When was Python created?'")

    result = await retriever.retrieve(
        query="When was Python created?",
        limit=2,
    )

    print(f"\nFound {len(result.documents)} relevant chunks:")
    for i, doc_result in enumerate(result.documents, 1):
        print(f"\n  Result {i} (score: {doc_result.score:.4f}):")
        content = doc_result.document.content[:200]
        print(f"  {content}...")

    # Use retrieve_text for formatted output
    print("\n" + "-" * 40)
    print("Using retrieve_text() for clean output:")

    text = await retriever.retrieve_text(
        query="What is Oracle Cloud?",
        limit=2,
    )
    print(f"\n{text[:300]}...")


# =============================================================================
# Step 4: RAG with Metadata Filtering
# =============================================================================


async def rag_with_metadata():
    """
    Metadata allows you to filter results beyond just similarity.

    Use cases:
    - Filter by document type (pdf, html, code)
    - Filter by date range
    - Filter by author or department
    - Filter by category or tags
    """
    print("\n" + "=" * 60)
    print("Tutorial 22: RAG with Metadata")
    print("=" * 60)

    from locus.rag import RAGRetriever
    from locus.rag.stores.memory import InMemoryVectorStore

    embedder = get_embedder()
    store = InMemoryVectorStore(dimension=embedder.config.dimension)
    retriever = RAGRetriever(embedder=embedder, store=store)

    # Add documents with different categories
    documents = [
        (
            "Python supports async/await syntax for concurrency.",
            {"category": "programming", "language": "python"},
        ),
        ("Use pip to install Python packages.", {"category": "programming", "language": "python"}),
        (
            "JavaScript uses async/await for async operations.",
            {"category": "programming", "language": "javascript"},
        ),
        ("Set up Oracle Database with these steps.", {"category": "database", "type": "oracle"}),
        ("PostgreSQL is an open-source database.", {"category": "database", "type": "postgresql"}),
    ]

    print("Adding categorized documents...")
    for content, metadata in documents:
        await retriever.add_document(content, metadata=metadata)
        print(f"  Added: {content[:40]}... [{metadata}]")

    # Search with metadata filter (if supported by store)
    print("\n" + "-" * 40)
    print("Searching for 'async programming'...")

    result = await retriever.retrieve("async programming", limit=3)

    print("\nAll results:")
    for doc_result in result.documents:
        print(f"  Score: {doc_result.score:.4f} | {doc_result.document.content[:50]}...")
        print(f"    Metadata: {doc_result.document.metadata}")


# =============================================================================
# Helper Functions
# =============================================================================


def get_embedder():
    """Get embedder based on available credentials."""
    # Try OpenAI first
    if os.environ.get("OPENAI_API_KEY"):
        from locus.rag.embeddings import OpenAIEmbeddings

        return OpenAIEmbeddings(model="text-embedding-3-small")

    # Try OCI GenAI. OCIEmbeddings auto-derives the endpoint from
    # LOCUS_OCI_REGION / OCI_REGION (falls back to the profile region,
    # then us-chicago-1) when service_endpoint is left empty.
    if os.path.exists(os.path.expanduser("~/.oci/config")):
        try:
            from locus.rag.embeddings import OCIEmbeddings

            return OCIEmbeddings(
                model_id="cohere.embed-english-v3.0",
                profile_name=os.getenv("LOCUS_OCI_PROFILE", os.getenv("OCI_PROFILE", "DEFAULT")),
                auth_type=os.getenv("LOCUS_OCI_AUTH_TYPE", os.getenv("OCI_AUTH_TYPE", "api_key")),
                compartment_id=os.getenv("LOCUS_OCI_COMPARTMENT", os.getenv("OCI_COMPARTMENT", "")),
                service_endpoint=os.getenv("LOCUS_OCI_ENDPOINT", os.getenv("OCI_ENDPOINT", "")),
            )
        except Exception:
            pass

    raise RuntimeError("No embedding credentials found. Set OPENAI_API_KEY or configure OCI.")


# =============================================================================
# Main
# =============================================================================


async def main():
    """Run all examples."""
    await understand_embeddings()
    await using_vector_stores()
    await using_rag_retriever()
    await rag_with_metadata()

    print("\n" + "=" * 60)
    print("Tutorial 22 Complete!")
    print("=" * 60)
    print("\nKey concepts covered:")
    print("  - Embeddings convert text to vectors")
    print("  - Similar texts have similar vectors")
    print("  - Vector stores enable fast similarity search")
    print("  - RAGRetriever simplifies the entire pipeline")
    print("\nNext: Try tutorial_23_rag_providers.py for different embedding providers")


if __name__ == "__main__":
    asyncio.run(main())
