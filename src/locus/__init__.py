# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""
Locus - A zero-LangChain agentic SDK.

Built-in Reflexion, Grounding Evaluation, and production-grade orchestration.
100% Pydantic. No magic.

Usage:
    from locus import Agent, tool

    @tool
    def search(query: str) -> str:
        '''Search the knowledge base.'''
        return "results..."

    agent = Agent(
        model="openai:gpt-4o",  # or oci:cohere.command-r-plus
        tools=[search],
        system_prompt="You are a helpful assistant.",
    )

    async for event in agent.run("Find information about X"):
        print(event)
"""

from locus.core.config import LocusSettings
from locus.core.errors import LocusError
from locus.core.events import (
    GroundingEvent,
    LocusEvent,
    ReflectEvent,
    TerminateEvent,
    ThinkEvent,
    ToolCompleteEvent,
    ToolStartEvent,
)
from locus.core.messages import Message, Role, ToolCall
from locus.core.state import AgentState
from locus.tools.context import ToolContext
from locus.tools.decorator import tool


# Lazy import mapping for optional dependencies
_LAZY_IMPORTS = {
    "Agent": ("locus.agent.agent", "Agent"),
    "AgentConfig": ("locus.agent.config", "AgentConfig"),
    "AgentResult": ("locus.agent.result", "AgentResult"),
    "Reflexion": ("locus.reasoning.reflexion", "Reflexion"),
    "GroundingEvaluator": ("locus.reasoning.grounding", "GroundingEvaluator"),
    "CausalChain": ("locus.reasoning.causal", "CausalChain"),
    "HookProvider": ("locus.hooks.provider", "HookProvider"),
    "HookRegistry": ("locus.hooks.registry", "HookRegistry"),
    # RAG
    "RAGRetriever": ("locus.rag.retriever", "RAGRetriever"),
    "OCIEmbeddings": ("locus.rag.embeddings.oci", "OCIEmbeddings"),
    "OracleVectorStore": ("locus.rag.stores.oracle", "OracleVectorStore"),
}


def __getattr__(name: str) -> object:
    """Lazy import for Agent and model classes."""
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, attr_name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__version__ = "0.1.0"
__all__ = [
    "Agent",
    "AgentConfig",
    "AgentResult",
    "AgentState",
    "CausalChain",
    "GroundingEvaluator",
    "GroundingEvent",
    "HookProvider",
    "HookRegistry",
    "LocusError",
    "LocusEvent",
    "LocusSettings",
    "Message",
    "ReflectEvent",
    "Reflexion",
    "Role",
    "TerminateEvent",
    "ThinkEvent",
    "ToolCall",
    "ToolCompleteEvent",
    "ToolContext",
    "ToolStartEvent",
    "__version__",
    "tool",
    # RAG (lazy)
    "RAGRetriever",
    "OCIEmbeddings",
    "OracleVectorStore",
]
