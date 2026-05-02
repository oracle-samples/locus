# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Example AgentServer entrypoint for container deployments.

This module is the import target for the Dockerfile's CMD:

    CMD ["uvicorn", "app:server.app", "--host", "0.0.0.0", "--port", "8080"]

Wire your real Agent here — register tools, set the model, attach a
checkpointer. The pattern below is a minimal travel-concierge with an
OCI bucket checkpointer; replace with whatever your workload needs.
"""

from __future__ import annotations

import os

from locus import Agent
from locus.memory.backends.oci_bucket import OCIBucketBackend
from locus.server import AgentServer
from locus.tools.decorator import tool


# ---------------------------------------------------------------------------
# Tools — replace with your domain.
# ---------------------------------------------------------------------------
@tool
def search_flights(origin: str, destination: str, date: str) -> list[dict]:
    """Search the GDS for available flights."""
    # Stub. Wire to your real flight API.
    return [
        {"flight_id": "AA-181", "origin": origin, "destination": destination, "date": date},
    ]


@tool(idempotent=True)
def book_flight(flight_id: str, customer_id: str) -> dict:
    """Book a flight. Re-fires return the cached receipt — never double-charge."""
    # Stub. Wire to your real billing system.
    return {"confirmation": "BK-58291", "flight_id": flight_id}


# ---------------------------------------------------------------------------
# Checkpointer — durable threads in OCI Object Storage.
# ---------------------------------------------------------------------------
checkpointer = OCIBucketBackend(
    bucket_name=os.environ["LOCUS_OCI_BUCKET_NAME"],
    namespace=os.environ["LOCUS_OCI_NAMESPACE"],
    prefix=os.environ.get("LOCUS_OCI_BUCKET_PREFIX", "locus/threads/"),
    auth_type=os.environ.get("OCI_AUTH_TYPE", "api_key"),
)


# ---------------------------------------------------------------------------
# Agent.
# ---------------------------------------------------------------------------
agent = Agent(
    model=os.environ.get("LOCUS_MODEL", "oci:openai.gpt-5"),
    tools=[search_flights, book_flight],
    system_prompt="You are a travel concierge. Find a flight, then book it.",
    checkpointer=checkpointer,
)


# ---------------------------------------------------------------------------
# Server. Bearer-token auth + per-principal thread isolation.
# ---------------------------------------------------------------------------
server = AgentServer(
    agent=agent,
    api_key=os.environ.get("LOCUS_SERVER_API_KEY"),
    title="Travel Concierge",
)


# Module-level export for uvicorn:
#     uvicorn app:server.app --host 0.0.0.0 --port 8080
app = server.app
