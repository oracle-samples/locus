# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Agent server — expose agents as HTTP endpoints.

Wraps a Locus Agent as a FastAPI application with invoke and stream
endpoints. Requires `fastapi` and `uvicorn` optional dependencies.

Example:
    from locus.agent import Agent, AgentConfig
    from locus.server import AgentServer

    agent = Agent(config=AgentConfig(
        system_prompt="You are a helpful assistant.",
        model=my_model,
    ))

    server = AgentServer(agent=agent)
    server.run(port=8000)
"""

from locus.server.app import AgentServer


__all__ = ["AgentServer"]
