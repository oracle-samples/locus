# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 24: RAG Agents - Building Knowledge-Augmented Agents

This tutorial shows how to build agents that can search and use
knowledge from your documents using RAG.

What you'll learn:
- Converting RAG retriever to an agent tool
- Building a RAG-powered Q&A agent
- Combining RAG with other tools
- Best practices for RAG agents

Prerequisites:
- Set OPENAI_API_KEY environment variable, or
- Have OCI config with DEFAULT profile

Run:
    python examples/tutorial_24_rag_agents.py
"""

import ast
import asyncio
import operator as _op
import os


_SAFE_MATH_BIN_OPS = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.FloorDiv: _op.floordiv,
    ast.Mod: _op.mod,
    ast.Pow: _op.pow,
}
_SAFE_MATH_UNARY_OPS = {ast.USub: _op.neg, ast.UAdd: _op.pos}


def _safe_math_eval(expression: str) -> float:
    """AST-based arithmetic evaluator. No names, calls, or attribute access allowed."""
    tree = ast.parse(expression, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_MATH_BIN_OPS:
            return _SAFE_MATH_BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_MATH_UNARY_OPS:
            return _SAFE_MATH_UNARY_OPS[type(node.op)](_eval(node.operand))
        raise ValueError("Unsupported expression")

    return _eval(tree)


# =============================================================================
# Why RAG Agents?
# =============================================================================

"""
RAG Agents combine the power of LLMs with your private knowledge.

Benefits:
- Answer questions about your documents
- Always grounded in source material
- Can cite sources for answers
- Combines knowledge search with reasoning

Use Cases:
- Customer support bots with product knowledge
- Internal Q&A systems for company docs
- Research assistants for paper analysis
- Code documentation helpers
"""


# =============================================================================
# Step 1: RAG as a Tool
# =============================================================================


async def rag_as_tool():
    """
    Convert a RAG retriever into a tool that agents can use.

    The retriever.as_tool() method creates a callable tool
    that the agent can invoke to search for information.
    """
    print("=" * 60)
    print("Tutorial 24: RAG as a Tool")
    print("=" * 60)

    from locus.rag import RAGRetriever
    from locus.rag.stores.memory import InMemoryVectorStore

    embedder = get_embedder()
    if not embedder:
        return

    store = InMemoryVectorStore(dimension=embedder.config.dimension)
    retriever = RAGRetriever(embedder=embedder, store=store)

    # Add some knowledge
    knowledge = [
        "Locus is a Python framework for building AI agents.",
        "Locus supports multiple LLM providers including OpenAI and OCI GenAI.",
        "Agents in Locus can use tools to interact with external systems.",
        "RAG in Locus enables agents to search through documents.",
        "Locus uses async/await for efficient concurrent operations.",
    ]

    print("Building knowledge base...")
    await retriever.add_documents(knowledge)
    print(f"  Added {len(knowledge)} documents")

    # Create a tool from the retriever
    search_tool = retriever.as_tool(
        name="search_knowledge",
        description="Search the knowledge base for information about Locus.",
    )

    print(f"
Created tool: {search_tool.name}")
    print(f"Description: {search_tool.description}")

    # Test the tool directly
    print("
" + "-" * 40)
    print("Testing tool directly...")

    result = await search_tool("What LLM providers does Locus support?")

    print("
Query: 'What LLM providers does Locus support?'")
    print(f"Results found: {result['total']}")
    for i, doc in enumerate(result["results"], 1):
        print(f"  {i}. Score: {doc['score']:.4f}")
        print(f"     {doc['content'][:60]}...")


# =============================================================================
# Step 2: Simple RAG Agent
# =============================================================================


async def simple_rag_agent():
    """
    Build a simple agent that can search and answer questions.
    """
    print("
" + "=" * 60)
    print("Tutorial 24: Simple RAG Agent")
    print("=" * 60)

    from locus.agent import Agent
    from locus.rag import RAGRetriever
    from locus.rag.stores.memory import InMemoryVectorStore

    embedder = get_embedder()
    model = get_model()
    if not embedder or not model:
        return

    store = InMemoryVectorStore(dimension=embedder.config.dimension)
    retriever = RAGRetriever(embedder=embedder, store=store)

    # Build a knowledge base about a fictional product
    product_docs = [
        """
        ProductX is an enterprise data platform launched in 2024.
        It supports real-time data processing at scale.
        ProductX can handle up to 1 million events per second.
        """,
        """
        ProductX pricing starts at $500/month for the starter plan.
        The enterprise plan costs $5000/month and includes support.
        All plans include a 30-day free trial.
        """,
        """
        ProductX integrates with popular tools like Kafka, Spark, and Flink.
        It provides REST APIs for custom integrations.
        SDKs are available for Python, Java, and Go.
        """,
        """
        ProductX requires a minimum of 4 CPU cores and 8GB RAM.
        For production, we recommend 16 cores and 32GB RAM.
        Cloud deployment is available on AWS, GCP, and Oracle Cloud.
        """,
    ]

    print("Building product knowledge base...")
    await retriever.add_documents(product_docs)

    # Create tool
    search_tool = retriever.as_tool(
        name="search_product_docs",
        description="Search ProductX documentation for information about features, pricing, requirements, and integrations.",
    )

    # Create agent with the tool
    agent = Agent(
        model=model,
        tools=[search_tool],
        system_prompt="""You are a helpful product assistant for ProductX.

When users ask questions:
1. Use the search_product_docs tool to find relevant information
2. Answer based on the search results
3. Be concise and accurate
4. If you can't find the answer, say so

Always cite information from the documentation.""",
        max_iterations=3,
    )

    # Test the agent
    questions = [
        "How much does ProductX cost?",
        "What are the system requirements?",
    ]

    for question in questions:
        print("
" + "-" * 40)
        print(f"User: {question}")

        # run_sync returns AgentResult directly
        result = agent.run_sync(question)

        print(f"Agent: {result.message}")


# =============================================================================
# Step 3: Multi-Tool RAG Agent
# =============================================================================


async def multi_tool_rag_agent():
    """
    Build an agent that combines RAG with other tools.

    This agent can:
    - Search knowledge base
    - Perform calculations
    - Get current date
    """
    print("
" + "=" * 60)
    print("Tutorial 24: Multi-Tool RAG Agent")
    print("=" * 60)

    from datetime import datetime

    from locus.agent import Agent
    from locus.rag import RAGRetriever
    from locus.rag.stores.memory import InMemoryVectorStore
    from locus.tools import tool

    embedder = get_embedder()
    model = get_model()
    if not embedder or not model:
        return

    store = InMemoryVectorStore(dimension=embedder.config.dimension)
    retriever = RAGRetriever(embedder=embedder, store=store)

    # Add financial knowledge
    finance_docs = [
        "Company ABC reported revenue of $10.5 billion in Q3 2024.",
        "Company ABC has 15,000 employees worldwide.",
        "Company ABC stock price is currently $150 per share.",
        "Company ABC was founded in 2010 in San Francisco.",
        "Company ABC expects 15% revenue growth in 2025.",
    ]

    await retriever.add_documents(finance_docs)

    # Define additional tools
    @tool
    def calculate(expression: str) -> str:
        """Evaluate a mathematical expression. Example: calculate('150 * 1000')"""
        try:
            return f"Result: {_safe_math_eval(expression)}"
        except (ValueError, SyntaxError, ZeroDivisionError) as e:
            return f"Error: {e}"

    @tool
    def get_current_date() -> str:
        """Get the current date and time."""
        return f"Current date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # Create RAG tool
    search_tool = retriever.as_tool(
        name="search_company_info",
        description="Search for information about Company ABC including financials, employees, and history.",
    )

    # Create agent with multiple tools
    agent = Agent(
        model=model,
        tools=[search_tool, calculate, get_current_date],
        system_prompt="""You are a financial analyst assistant.

You have access to:
- search_company_info: Search company documentation
- calculate: Perform mathematical calculations
- get_current_date: Get current date

Use tools as needed to answer questions accurately.""",
        max_iterations=5,
    )

    # Test complex queries
    queries = [
        "What is Company ABC's revenue?",
        "If the stock price doubles, what would it be?",
        "How old is Company ABC today?",
    ]

    for query in queries:
        print("
" + "-" * 40)
        print(f"User: {query}")

        # run_sync returns AgentResult directly
        result = agent.run_sync(query)

        print(f"Agent: {result.message}")


# =============================================================================
# Step 4: RAG with Streaming
# =============================================================================


async def rag_with_streaming():
    """
    Stream RAG agent responses for better UX.
    """
    print("
" + "=" * 60)
    print("Tutorial 24: RAG with Streaming")
    print("=" * 60)

    from locus.agent import Agent
    from locus.core.events import ThinkEvent, ToolCompleteEvent, ToolStartEvent
    from locus.rag import RAGRetriever
    from locus.rag.stores.memory import InMemoryVectorStore

    embedder = get_embedder()
    model = get_model()
    if not embedder or not model:
        return

    store = InMemoryVectorStore(dimension=embedder.config.dimension)
    retriever = RAGRetriever(embedder=embedder, store=store)

    # Add knowledge
    docs = [
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning models learn patterns from data.",
        "Neural networks are inspired by biological neurons.",
    ]
    await retriever.add_documents(docs)

    search_tool = retriever.as_tool(name="search", description="Search documents")

    agent = Agent(
        model=model,
        tools=[search_tool],
        system_prompt="Search for information and provide helpful answers.",
        max_iterations=2,
    )

    print("Streaming agent response...
")

    async for event in agent.run("What do neural networks do?"):
        if isinstance(event, ToolStartEvent):
            print(f"[Tool] Searching: {event.tool_name}...")
        elif isinstance(event, ToolCompleteEvent):
            print(f"[Tool] Found {len(event.result.get('results', []))} results")
        elif isinstance(event, ThinkEvent):
            print(f"[Agent] {event.reasoning[:100]}...")


# =============================================================================
# Step 5: Best Practices
# =============================================================================


async def rag_best_practices():
    """
    Demonstrate RAG best practices.
    """
    print("
" + "=" * 60)
    print("Tutorial 24: RAG Best Practices")
    print("=" * 60)

    print("""
Best Practices for RAG Agents:

1. CHUNK SIZE MATTERS
   - Too small: Lose context
   - Too large: Dilute relevance
   - Recommended: 500-1000 characters with 50-100 overlap

2. QUALITY OVER QUANTITY
   - Clean your documents before indexing
   - Remove boilerplate, headers, footers
   - Keep source metadata for citations

3. PROMPT ENGINEERING
   - Tell the agent when to search
   - Instruct it to cite sources
   - Handle "not found" gracefully

4. HYBRID APPROACHES
   - Combine keyword + semantic search
   - Use metadata filters to narrow scope
   - Rerank results for better precision

5. EVALUATION
   - Test with real user questions
   - Measure retrieval relevance
   - Track answer quality over time

6. PRODUCTION CONSIDERATIONS
   - Use persistent vector stores (Qdrant, OpenSearch)
   - Implement caching for embeddings
   - Monitor latency and costs
""")

    # Example of good prompt engineering
    print("-" * 40)
    print("Example System Prompt for RAG Agent:")
    print("-" * 40)
    print("""
You are a helpful assistant with access to a knowledge base.

INSTRUCTIONS:
1. When asked a question, ALWAYS search the knowledge base first
2. Base your answers ONLY on the search results
3. If search returns no relevant results, say "I couldn't find information about that"
4. Quote relevant passages when helpful
5. If multiple documents are relevant, synthesize the information

RESPONSE FORMAT:
- Start with a direct answer
- Provide supporting details from the documents
- End with "Source: [document reference]" if applicable
""")


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


def get_model():
    """Get LLM model using the shared tutorial config (honours all env vars)."""
    from config import get_model as _get_model

    return _get_model(max_tokens=512)


# =============================================================================
# Main
# =============================================================================


async def main():
    """Run all examples."""
    await rag_as_tool()
    await simple_rag_agent()
    await multi_tool_rag_agent()
    await rag_with_streaming()
    await rag_best_practices()

    print("
" + "=" * 60)
    print("Tutorial 24 Complete!")
    print("=" * 60)
    print("
You've learned how to:")
    print("  - Convert RAG retriever to an agent tool")
    print("  - Build Q&A agents with document search")
    print("  - Combine RAG with other tools")
    print("  - Stream RAG agent responses")
    print("  - Apply RAG best practices")
    print("
Congratulations! You've completed the RAG tutorials.")


if __name__ == "__main__":
    asyncio.run(main())
