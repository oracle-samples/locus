# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Agent-to-Agent (A2A) protocol for cross-framework interop.

Enables Locus agents to communicate with agents from other frameworks
(Strands, ADK, etc.) using a standard message format.

- A2AServer: Expose a Locus agent as an A2A-compatible endpoint
- A2AClient: Call a remote A2A agent from Locus
"""

from locus.a2a.protocol import A2AClient, A2AServer


__all__ = ["A2AClient", "A2AServer"]
