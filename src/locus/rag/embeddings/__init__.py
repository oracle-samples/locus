# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Embedding providers for RAG.

Available providers:
- OCIEmbeddings: OCI GenAI with Cohere models (recommended for Oracle)
- OpenAIEmbeddings: OpenAI text-embedding models
"""

from locus.rag.embeddings.base import (
    BaseEmbedding,
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
)


__all__ = [
    # Base
    "BaseEmbedding",
    "EmbeddingConfig",
    "EmbeddingProvider",
    "EmbeddingResult",
    # Providers (lazy imports)
    "OCIEmbeddings",
    "OpenAIEmbeddings",
]


def __getattr__(name: str):
    """Lazy import providers to avoid requiring all dependencies."""
    if name == "OCIEmbeddings":
        from locus.rag.embeddings.oci import OCIEmbeddings

        return OCIEmbeddings

    if name == "OpenAIEmbeddings":
        from locus.rag.embeddings.openai import OpenAIEmbeddings

        return OpenAIEmbeddings

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
