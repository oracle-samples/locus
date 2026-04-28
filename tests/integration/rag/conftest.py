# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Shared fixtures and configuration for RAG integration tests.

All configuration is via environment variables - nothing is hardcoded.

Required for OCI tests:
- OCI_PROFILE: OCI config profile name (REQUIRED)
- OCI_AUTH_TYPE: Auth type - api_key, security_token, etc. (default: api_key)
- OCI_COMPARTMENT_ID: Compartment OCID (optional, uses tenancy if not set)

Required for OpenSearch tests:
- OPENSEARCH_HOSTS: Comma-separated OpenSearch hosts (REQUIRED)
- OPENSEARCH_USER: OpenSearch username (REQUIRED)
- OPENSEARCH_PASSWORD: OpenSearch password (REQUIRED)
- OPENSEARCH_USE_SSL: Use SSL (default: true)
- OPENSEARCH_VERIFY_CERTS: Verify certs (default: false)

Required for Qdrant tests:
- QDRANT_URL: Qdrant server URL (default: http://localhost:6333)
- QDRANT_API_KEY: API key for Qdrant Cloud (optional)
"""

import os

import pytest


def get_oci_config():
    """Get OCI configuration from environment.

    Required environment variables:
    - OCI_PROFILE: OCI config profile name (no default - must be set)
    - OCI_AUTH_TYPE: Auth type (api_key, security_token, etc.)
    - OCI_COMPARTMENT_ID: Compartment OCID (optional; also accepts OCI_COMPARTMENT)
    - OCI_ENDPOINT: Full GenAI service endpoint (optional, overrides profile region)
    """
    profile = os.environ.get("OCI_PROFILE")
    if not profile:
        raise ValueError(
            "OCI_PROFILE environment variable must be set. Example: export OCI_PROFILE=MY_PROFILE"
        )
    # Accept both OCI_COMPARTMENT_ID (historic) and OCI_COMPARTMENT (what the
    # rest of the suite uses) so a single export set drives every test file.
    compartment = os.environ.get("OCI_COMPARTMENT_ID") or os.environ.get("OCI_COMPARTMENT") or ""
    return {
        "profile_name": profile,
        "auth_type": os.environ.get("OCI_AUTH_TYPE", "api_key"),
        "compartment_id": compartment,
        "service_endpoint": os.environ.get("OCI_ENDPOINT"),
    }


def get_opensearch_config():
    """Get OpenSearch configuration from environment.

    Required environment variables:
    - OPENSEARCH_HOSTS: Comma-separated host list (e.g., "host1:9200,host2:9200")
    - OPENSEARCH_USER: Username
    - OPENSEARCH_PASSWORD: Password

    Optional:
    - OPENSEARCH_USE_SSL: Use SSL (default: true)
    - OPENSEARCH_VERIFY_CERTS: Verify certs (default: false)
    """
    hosts_str = os.environ.get("OPENSEARCH_HOSTS")
    if not hosts_str:
        raise ValueError(
            "OPENSEARCH_HOSTS environment variable must be set. "
            "Example: export OPENSEARCH_HOSTS=localhost:9200"
        )

    user = os.environ.get("OPENSEARCH_USER")
    password = os.environ.get("OPENSEARCH_PASSWORD")
    if not user or not password:
        raise ValueError(
            "OPENSEARCH_USER and OPENSEARCH_PASSWORD environment variables must be set."
        )

    hosts = [h.strip() for h in hosts_str.split(",")]

    return {
        "hosts": hosts,
        "http_auth": (user, password),
        "use_ssl": os.environ.get("OPENSEARCH_USE_SSL", "true").lower() == "true",
        "verify_certs": os.environ.get("OPENSEARCH_VERIFY_CERTS", "false").lower() == "true",
    }


def get_qdrant_config():
    """Get Qdrant configuration from environment."""
    return {
        "url": os.environ.get("QDRANT_URL", "http://localhost:6333"),
        "api_key": os.environ.get("QDRANT_API_KEY"),
    }


@pytest.fixture
def oci_config():
    """OCI configuration fixture. Skips test if OCI_PROFILE not set."""
    try:
        return get_oci_config()
    except ValueError as e:
        pytest.skip(str(e))


@pytest.fixture
def opensearch_config():
    """OpenSearch configuration fixture. Skips test if env vars not set."""
    try:
        return get_opensearch_config()
    except ValueError as e:
        pytest.skip(str(e))


@pytest.fixture
def qdrant_config():
    """Qdrant configuration fixture. Skips test if qdrant-client not installed."""
    try:
        import qdrant_client  # noqa: F401
    except ImportError:
        pytest.skip("qdrant-client not installed. Install with: pip install qdrant-client")

    config = get_qdrant_config()

    # Check if Qdrant server is reachable
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=config["url"], api_key=config["api_key"])
        client.get_collections()  # Simple health check
    except Exception as e:
        pytest.skip(f"Qdrant server not reachable at {config['url']}: {e}")

    return config
