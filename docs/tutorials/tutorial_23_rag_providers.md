# Tutorial 23: RAG Providers - Embeddings and Vector Stores

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

## Source

```python
--8<-- "examples/tutorial_23_rag_providers.py"
```
