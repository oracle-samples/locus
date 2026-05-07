"""
Tutorial 23: RAG Providers - Embeddings and Vector Stores

This tutorial shows how to use different embedding providers
and vector stores for production RAG systems.

What you'll learn:
- OpenAI embeddings (text-embedding-3-small/large)
- OCI GenAI Cohere embeddings (cohere.embed-english-v3.0)
- Qdrant vector store (open-source, high performance)
- OpenSearch vector store (enterprise search)
- Choosing the right provider for your use case

Prerequisites:
- Set OPENAI_API_KEY environment variable, and/or
- Have OCI config with DEFAULT profile
- Docker for running Qdrant/OpenSearch (optional)

Run:
    python examples/tutorial_23_rag_providers.py
"""

import asyncio
import os


# =============================================================================
# Embedding Provider Comparison
# =============================================================================

"""
Embedding Providers Overview:

| Provider    | Dimension | Best For                    | Cost      |
|-------------|-----------|-----------------------------| ----------|
| OpenAI      | 1536/3072 | General purpose, high quality| Pay/token |
| Cohere (OCI)| 1024      | Enterprise, Oracle ecosystem | Pay/token |

Model Recommendations:
- OpenAI text-embedding-3-small: Fast, cheap, good quality (1536 dims)
- OpenAI text-embedding-3-large: Best quality, higher cost (3072 dims)
- Cohere embed-english-v3.0: Excellent for search (1024 dims)
- Cohere embed-multilingual-v3.0: Multiple languages (1024 dims)
"""


# =============================================================================
# Step 1: OpenAI Embeddings
# =============================================================================


async def openai_embeddings_example():
    """
    OpenAI provides high-quality embeddings via their API.

    Models:
    - text-embedding-3-small: 1536 dimensions, fast
    - text-embedding-3-large: 3072 dimensions, best quality
    - text-embedding-ada-002: Legacy, 1536 dimensions
    """
    print("=" * 60)
    print("Tutorial 23: OpenAI Embeddings")
    print("=" * 60)

    if not os.environ.get("OPENAI_API_KEY"):
        print("Skipping: OPENAI_API_KEY not set")
        return

    from locus.rag.embeddings import OpenAIEmbeddings

    # Create embedder with small model
    embedder = OpenAIEmbeddings(
        model="text-embedding-3-small",
        # dimensions=512,  # Optional: reduce dimensions
    )

    print("Model: text-embedding-3-small")
    print(f"Dimension: {embedder.config.dimension}")
    print(f"Max tokens: {embedder.config.max_tokens}")
    print(f"Batch size: {embedder.config.batch_size}")

    # Embed text
    result = await embedder.embed("OpenAI provides powerful AI models.")
    print("\nEmbedded text successfully")
    print(f"  Vector length: {len(result.embedding)}")
    print(f"  Model used: {result.model}")

    # Batch embedding
    texts = [
        "Machine learning is transforming industries.",
        "Natural language processing enables text understanding.",
        "Computer vision allows machines to see.",
    ]

    print(f"\nBatch embedding {len(texts)} texts...")
    results = await embedder.embed_batch(texts)
    print(f"  Embedded {len(results)} texts successfully")

    # Clean up
    await embedder.close()


# =============================================================================
# Step 2: OCI GenAI (Cohere) Embeddings
# =============================================================================


async def oci_cohere_embeddings_example():
    """
    OCI GenAI provides Cohere embeddings optimized for search.

    Models:
    - cohere.embed-english-v3.0: English, 1024 dimensions
    - cohere.embed-multilingual-v3.0: 100+ languages
    - cohere.embed-english-light-v3.0: Faster, 384 dimensions

    Features:
    - SEARCH_DOCUMENT type for indexing
    - SEARCH_QUERY type for queries
    - Automatic input type selection
    """
    print("\n" + "=" * 60)
    print("Tutorial 23: OCI GenAI (Cohere) Embeddings")
    print("=" * 60)

    if not os.path.exists(os.path.expanduser("~/.oci/config")):
        print("Skipping: OCI config not found")
        return

    try:
        from locus.rag.embeddings import OCIEmbeddings

        # OCIEmbeddings auto-derives the endpoint from LOCUS_OCI_REGION
        # / OCI_REGION when service_endpoint is left empty.
        embedder = OCIEmbeddings(
            model_id="cohere.embed-english-v3.0",
            profile_name=os.getenv("LOCUS_OCI_PROFILE", os.getenv("OCI_PROFILE", "DEFAULT")),
            auth_type=os.getenv("LOCUS_OCI_AUTH_TYPE", os.getenv("OCI_AUTH_TYPE", "api_key")),
            compartment_id=os.getenv("LOCUS_OCI_COMPARTMENT", os.getenv("OCI_COMPARTMENT", "")),
            service_endpoint=os.getenv("LOCUS_OCI_ENDPOINT", os.getenv("OCI_ENDPOINT", "")),
        )

        print("Model: cohere.embed-english-v3.0")
        print(f"Dimension: {embedder.config.dimension}")
        print(f"Batch size: {embedder.config.batch_size}")

        # Embed for document indexing
        print("\nEmbedding document...")
        doc_result = await embedder.embed("Oracle Cloud provides enterprise services.")
        print(f"  Vector length: {len(doc_result.embedding)}")

        # Embed for search query
        print("\nEmbedding query...")
        query_result = await embedder.embed_query("What cloud services are available?")
        print(f"  Vector length: {len(query_result.embedding)}")

        # Batch embed documents
        docs = [
            "OCI offers compute instances.",
            "Oracle Database runs in the cloud.",
            "Object Storage provides scalable storage.",
        ]

        print(f"\nBatch embedding {len(docs)} documents...")
        results = await embedder.embed_documents(docs)
        print(f"  Embedded {len(results)} documents successfully")

    except Exception as e:
        print(f"Skipping: {e}")


# =============================================================================
# Step 3: Qdrant Vector Store
# =============================================================================


async def qdrant_store_example():
    """
    Qdrant is a high-performance vector database.

    Features:
    - Fast similarity search
    - Metadata filtering
    - Horizontal scaling
    - Cloud or self-hosted

    Start Qdrant locally:
        docker run -p 6333:6333 qdrant/qdrant
    """
    print("\n" + "=" * 60)
    print("Tutorial 23: Qdrant Vector Store")
    print("=" * 60)

    try:
        from qdrant_client import QdrantClient

        # Check if Qdrant is running
        client = QdrantClient(url="http://localhost:6333")
        client.get_collections()
    except Exception:
        print("Skipping: Qdrant not available at localhost:6333")
        print("Start with: docker run -p 6333:6333 qdrant/qdrant")
        return

    from locus.rag import RAGRetriever
    from locus.rag.stores.qdrant import QdrantVectorStore

    embedder = get_embedder()
    if not embedder:
        return

    # Create Qdrant store
    store = QdrantVectorStore(
        url="http://localhost:6333",
        collection_name="tutorial_11_demo",
        dimension=embedder.config.dimension,
        # api_key="...",  # For Qdrant Cloud
    )

    print("Connected to Qdrant at localhost:6333")
    print("Collection: tutorial_11_demo")
    print(f"Dimension: {embedder.config.dimension}")

    # Create retriever
    retriever = RAGRetriever(embedder=embedder, store=store)

    # Clean up any existing data
    try:
        await store._ensure_collection()
        await store.clear()
    except Exception:
        pass

    # Add documents
    documents = [
        "Qdrant is written in Rust for maximum performance.",
        "Qdrant supports HNSW algorithm for fast search.",
        "You can filter Qdrant results by metadata.",
        "Qdrant Cloud provides managed hosting.",
    ]

    print("\nAdding documents...")
    await retriever.add_documents(documents)
    print(f"  Added {len(documents)} documents")

    # Search
    print("\n" + "-" * 40)
    query = "How does Qdrant achieve fast search?"
    print(f"Query: '{query}'")

    result = await retriever.retrieve(query, limit=2)

    print("\nResults:")
    for i, doc_result in enumerate(result.documents, 1):
        print(f"  {i}. Score: {doc_result.score:.4f}")
        print(f"     {doc_result.document.content}")

    # Clean up
    await store.clear()
    await store.close()
    print("\nCleanup complete")


# =============================================================================
# Step 4: OpenSearch Vector Store
# =============================================================================


async def opensearch_store_example():
    """
    OpenSearch provides enterprise vector search with k-NN plugin.

    Features:
    - Combines full-text search with vectors
    - Scalable and distributed
    - Rich query DSL
    - AWS and self-hosted options

    Start OpenSearch locally:
        docker run -p 9200:9200 -e "discovery.type=single-node" \\
            -e "OPENSEARCH_INITIAL_ADMIN_PASSWORD=Admin123!" \\
            opensearchproject/opensearch:2.11.0
    """
    print("\n" + "=" * 60)
    print("Tutorial 23: OpenSearch Vector Store")
    print("=" * 60)

    try:
        import httpx

        response = httpx.get(
            "http://localhost:9200",
            auth=("admin", "admin"),
            verify=False,
            timeout=5.0,
        )
        response.raise_for_status()
        # Verify it's actually OpenSearch/Elasticsearch — not just any HTTP service
        body = response.json()
        if "version" not in body or "cluster_name" not in body:
            raise RuntimeError("not an OpenSearch instance")
    except Exception:
        print("Skipping: OpenSearch not available at localhost:9200")
        print("Start with: docker-compose up opensearch")
        return

    from locus.rag import RAGRetriever
    from locus.rag.stores.opensearch import OpenSearchVectorStore

    embedder = get_embedder()
    if not embedder:
        return

    # Create OpenSearch store
    store = OpenSearchVectorStore(
        hosts=["localhost:9200"],
        http_auth=("admin", "admin"),
        use_ssl=False,
        index_name="tutorial_11_demo",
        dimension=embedder.config.dimension,
    )

    print("Connected to OpenSearch at localhost:9200")
    print("Index: tutorial_11_demo")
    print(f"Dimension: {embedder.config.dimension}")

    # Create retriever
    retriever = RAGRetriever(embedder=embedder, store=store)

    # Clean up any existing data
    try:
        await store._ensure_index()
        await store.clear()
    except Exception:
        pass

    # Add documents
    documents = [
        "OpenSearch is a fork of Elasticsearch.",
        "OpenSearch uses the k-NN plugin for vector search.",
        "You can combine BM25 text search with vector similarity.",
        "OpenSearch scales horizontally across clusters.",
    ]

    print("\nAdding documents...")
    await retriever.add_documents(documents)
    print(f"  Added {len(documents)} documents")

    # Search
    print("\n" + "-" * 40)
    query = "How does OpenSearch handle vector search?"
    print(f"Query: '{query}'")

    result = await retriever.retrieve(query, limit=2)

    print("\nResults:")
    for i, doc_result in enumerate(result.documents, 1):
        print(f"  {i}. Score: {doc_result.score:.4f}")
        print(f"     {doc_result.document.content}")

    # Clean up
    await store.clear()
    await store.close()
    print("\nCleanup complete")


# =============================================================================
# Step 5: Comparing Providers
# =============================================================================


async def compare_providers():
    """
    Compare embedding providers on the same text.
    """
    print("\n" + "=" * 60)
    print("Tutorial 23: Comparing Providers")
    print("=" * 60)

    import math

    def cosine_similarity(a, b):
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b)

    test_texts = [
        "Python is a programming language",
        "Python is used for data science",
        "Cats are domestic animals",
    ]

    providers = []

    # Try OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        from locus.rag.embeddings import OpenAIEmbeddings

        providers.append(("OpenAI", OpenAIEmbeddings(model="text-embedding-3-small")))

    # Try OCI
    if os.path.exists(os.path.expanduser("~/.oci/config")):
        try:
            from locus.rag.embeddings import OCIEmbeddings

            providers.append(
                (
                    "OCI Cohere",
                    OCIEmbeddings(
                        model_id="cohere.embed-english-v3.0",
                        profile_name=os.getenv(
                            "LOCUS_OCI_PROFILE", os.getenv("OCI_PROFILE", "DEFAULT")
                        ),
                        auth_type=os.getenv(
                            "LOCUS_OCI_AUTH_TYPE", os.getenv("OCI_AUTH_TYPE", "api_key")
                        ),
                        compartment_id=os.getenv(
                            "LOCUS_OCI_COMPARTMENT", os.getenv("OCI_COMPARTMENT", "")
                        ),
                        service_endpoint=os.getenv(
                            "LOCUS_OCI_ENDPOINT", os.getenv("OCI_ENDPOINT", "")
                        ),
                    ),
                )
            )
        except Exception:
            pass

    if not providers:
        print("No embedding providers available for comparison")
        return

    print(f"Comparing {len(providers)} provider(s) on similarity detection\n")
    print("Test texts:")
    for i, text in enumerate(test_texts):
        print(f"  [{i}] {text}")

    for name, embedder in providers:
        print(f"\n{'-' * 40}")
        print(f"Provider: {name} (dim={embedder.config.dimension})")

        results = await embedder.embed_batch(test_texts)

        sim_01 = cosine_similarity(results[0].embedding, results[1].embedding)
        sim_02 = cosine_similarity(results[0].embedding, results[2].embedding)

        print(f"  [0] vs [1] (both Python): {sim_01:.4f}")
        print(f"  [0] vs [2] (Python vs Cats): {sim_02:.4f}")
        print(f"  Difference: {sim_01 - sim_02:.4f}")

        if hasattr(embedder, "close"):
            await embedder.close()


# =============================================================================
# Helper Functions
# =============================================================================


def get_embedder():
    """Get embedder based on available credentials."""
    if os.environ.get("OPENAI_API_KEY"):
        from locus.rag.embeddings import OpenAIEmbeddings

        return OpenAIEmbeddings(model="text-embedding-3-small")

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

    print("No embedding credentials found")
    return None


# =============================================================================
# Main
# =============================================================================


async def main():
    """Run all examples."""
    await openai_embeddings_example()
    await oci_cohere_embeddings_example()
    await qdrant_store_example()
    await opensearch_store_example()
    await compare_providers()

    print("\n" + "=" * 60)
    print("Tutorial 23 Complete!")
    print("=" * 60)
    print("\nProvider Summary:")
    print("  OpenAI: Great quality, simple API, pay-per-use")
    print("  OCI Cohere: Enterprise-ready, Oracle ecosystem")
    print("  Qdrant: Fast, simple, great for startups")
    print("  OpenSearch: Enterprise, combines text + vector search")
    print("\nNext: Try tutorial_24_rag_agents.py to build RAG-powered agents")


if __name__ == "__main__":
    asyncio.run(main())
