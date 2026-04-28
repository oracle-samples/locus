# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Checkpoint backends for Locus.

Available backends:
- MemoryCheckpointer: In-memory storage for testing/development
- FileCheckpointer: Local file-based storage
- HTTPCheckpointer: Remote HTTP API storage
- SQLiteBackend: Local SQLite database
- RedisBackend: Redis key-value store
- PostgreSQLBackend: PostgreSQL database with JSONB support
- OpenSearchBackend: OpenSearch with full-text search
- OCIBucketBackend: OCI Object Storage for cloud deployments
- OracleBackend: Oracle Database with JSON support

Usage:
    ```python
    from locus.memory.backends import (
        MemoryCheckpointer,
        SQLiteBackend,
        RedisBackend,
    )

    # For testing
    checkpointer = MemoryCheckpointer()

    # For local persistence
    checkpointer = SQLiteBackend("./checkpoints.db")

    # For production (choose based on your infrastructure)
    checkpointer = RedisBackend("redis://localhost:6379")
    checkpointer = PostgreSQLBackend(host="localhost", database="myapp")
    checkpointer = OpenSearchBackend(hosts=["localhost:9200"])
    checkpointer = OCIBucketBackend(bucket_name="checkpoints", namespace="myns")
    checkpointer = OracleBackend(dsn="mydb_high", user="admin", password="secret")
    ```
"""

from locus.memory.backends.adapters import (
    StorageBackendAdapter,
    oci_bucket_checkpointer,
    opensearch_checkpointer,
    oracle_checkpointer,
    postgresql_checkpointer,
    redis_checkpointer,
    sqlite_checkpointer,
)
from locus.memory.backends.file import FileCheckpointer
from locus.memory.backends.http import HTTPCheckpointer
from locus.memory.backends.memory import MemoryCheckpointer
from locus.memory.backends.oci_bucket import OCIBucketBackend
from locus.memory.backends.opensearch import OpenSearchBackend
from locus.memory.backends.oracle import OracleBackend
from locus.memory.backends.postgresql import PostgreSQLBackend
from locus.memory.backends.redis import RedisBackend
from locus.memory.backends.sqlite import SQLiteBackend


__all__ = [
    # Full checkpointers (BaseCheckpointer interface)
    "FileCheckpointer",
    "HTTPCheckpointer",
    "MemoryCheckpointer",
    # Storage backends (simple dict interface)
    "OCIBucketBackend",
    "OpenSearchBackend",
    "OracleBackend",
    "PostgreSQLBackend",
    "RedisBackend",
    "SQLiteBackend",
    # Adapter and factory functions
    "StorageBackendAdapter",
    "oci_bucket_checkpointer",
    "opensearch_checkpointer",
    "oracle_checkpointer",
    "postgresql_checkpointer",
    "redis_checkpointer",
    "sqlite_checkpointer",
]
