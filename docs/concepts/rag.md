# RAG

RAG in locus is three small pieces — an **embedder**, a **vector
store**, and a **retriever** that wires them — plus a one-liner to
expose the retriever as a tool.

```python
from locus.rag import RAGRetriever, OCIEmbeddings, OracleVectorStore

retriever = RAGRetriever(
    embedder=OCIEmbeddings(
        model_id="cohere.embed-english-v3.0",
        service_endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
    ),
    store=OracleVectorStore(
        dsn="mydb_high",
        user="ADMIN",
        password=...,
        dimension=1024,
        wallet_location="~/.oci/wallets/mydb",
    ),
)

await retriever.add_file("manual.pdf")
hits = await retriever.retrieve("How do I rotate API keys?", limit=5)

agent = Agent(model=..., tools=[retriever.as_tool()])
```

`as_tool()` returns a tool the model decides when to call. The model
asks the question; the retriever embeds, searches, and returns ranked
passages.

## Embedders

| Class | Provider |
|---|---|
| `OCIEmbeddings` | Cohere via OCI GenAI (English / Multilingual / Image / v4) |
| `OpenAIEmbeddings` | `text-embedding-3-small`, `-large` |

## Vector stores

| Store | Class | Notes |
|---|---|---|
| **Oracle 26ai** | `OracleVectorStore` | Native `VECTOR(N, FLOAT32)` + `VECTOR_DISTANCE`; the day-1 target. |
| OpenSearch | `OpenSearchVectorStore` | k-NN index. |
| Qdrant | `QdrantVectorStore` | |
| Pinecone | `PineconeVectorStore` | |
| pgvector | `PgVectorStore` | |
| Chroma | `ChromaVectorStore` | |
| In-memory | `InMemoryVectorStore` | Dev/tests. |

## Multimodal ingestion

`retriever.add_file(path)` dispatches by file type:

- **PDF** — text extraction + OCR for image-bearing pages.
- **Image** — OCR (Tesseract / OCI Vision).
- **Audio** — transcription via OCI Speech or Whisper.
- **Text / Markdown / Code** — direct chunking.

## Hybrid retrieval

Set `RAGRetriever(retrieval="hybrid")` to combine semantic similarity
with BM25 keyword matching, then re-rank with `cohere.rerank-v3.5` if
a reranker is configured. The store has to support keyword search —
Oracle 26ai and OpenSearch do.

## When to use

- The agent needs facts you have but the model wasn't trained on.
- Document size exceeds the model's context window.
- You want grounded answers with citations.

## Tutorials

- [`tutorial_22_rag_basics.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_22_rag_basics.py)
- [`tutorial_23_rag_providers.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_23_rag_providers.py)
- [`tutorial_24_rag_agents.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_24_rag_agents.py)

## Source

`src/locus/rag/`.
