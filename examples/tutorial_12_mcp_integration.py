"""
Tutorial 12: MCP Integration

This tutorial covers:
- Exposing Locus agents as MCP servers
- Connecting to external MCP servers
- Converting between Locus and MCP tools
- Building MCP-compatible agents

Prerequisites: Tutorial 11 (Swarm Multi-Agent)
Difficulty: Advanced

Note: MCP (Model Context Protocol) allows AI assistants to use external tools.
See https://modelcontextprotocol.io for the specification.
"""

import ast
import asyncio
import json
import operator as _op

# Import shared config for model
from config import get_model, print_config

from locus.agent import Agent
from locus.integrations.fastmcp import (
    LocusMCPServer,
    create_mcp_server,
    locus_tool_to_mcp,
)
from locus.tools import tool


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
# Part 1: Creating Locus Tools
# =============================================================================


@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    # Simulated weather data
    weather_data = {
        "new york": {"temp": 72, "condition": "sunny"},
        "london": {"temp": 55, "condition": "cloudy"},
        "tokyo": {"temp": 68, "condition": "partly cloudy"},
    }
    data = weather_data.get(city.lower(), {"temp": 70, "condition": "unknown"})
    return f"Weather in {city}: {data['temp']}°F, {data['condition']}"


@tool
def search_database(query: str, limit: int = 5) -> list[dict]:
    """Search the database for matching records."""
    # Simulated database
    return [
        {"id": 1, "title": f"Result for '{query}' - Item 1"},
        {"id": 2, "title": f"Result for '{query}' - Item 2"},
    ][:limit]


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        return str(_safe_math_eval(expression))
    except (ValueError, SyntaxError, ZeroDivisionError):
        return "Error: Invalid expression"


def example_locus_tools():
    """Create and inspect Locus tools."""
    print("=== Part 1: Locus Tools ===\n")

    print("Tool: get_weather")
    print(f"  Name: {get_weather.name}")
    print(f"  Description: {get_weather.description}")
    print(f"  Parameters: {json.dumps(get_weather.parameters, indent=4)}")

    print("\nDirect execution:")
    result = get_weather("Tokyo")
    print(f"  get_weather('Tokyo') = {result}")
    print()


# =============================================================================
# Part 2: Converting Tools to MCP Format
# =============================================================================


def example_tool_conversion():
    """Convert Locus tools to MCP format and back."""
    print("=== Part 2: Tool Conversion ===\n")

    # Convert Locus tool to MCP schema
    mcp_schema = locus_tool_to_mcp(get_weather)

    print("Locus tool converted to MCP schema:")
    print(json.dumps(mcp_schema, indent=2))
    print()

    # MCP tools can be converted back to Locus
    print("MCP tools can be converted to Locus tools using mcp_tool_to_locus()")
    print("This allows using external MCP server tools in Locus agents.")
    print()


# =============================================================================
# Part 3: Creating an MCP Server
# =============================================================================


def example_mcp_server():
    """Create an MCP server from a Locus agent."""
    print("=== Part 3: MCP Server ===\n")

    model = get_model(max_tokens=200)

    # Create a Locus agent with tools
    agent = Agent(
        model=model,
        tools=[get_weather, search_database, calculate],
        system_prompt="You are a helpful assistant with access to weather, search, and calculator tools.",
    )

    # Create MCP server from the agent
    server = create_mcp_server(
        agent=agent,
        name="locus-assistant",
        version="1.0.0",
    )

    print(f"MCP Server created: {server.name} v{server.version}")
    print("Agent tools will be exposed as MCP tools")
    print()

    print("To run the server:")
    print("  server.run()  # Starts stdio transport")
    print("  server.run(transport='sse')  # Starts SSE transport")
    print()

    print("The server exposes:")
    print("  - All agent tools (get_weather, search_database, calculate)")
    print("  - run_agent(prompt) - Run the full agent")
    print("  - run_agent_stream(prompt) - Run with streaming")
    print()

    return server


# =============================================================================
# Part 4: Handling MCP Requests
# =============================================================================


async def example_mcp_requests():
    """Handle MCP requests programmatically."""
    print("=== Part 4: MCP Requests ===\n")

    try:
        import fastmcp  # noqa: F401
    except ImportError:
        print("Note: fastmcp package not installed.")
        print("Install with: pip install fastmcp")
        print()
        print("Without fastmcp, the server structure is shown but requests can't be processed.")
        print("The server.handle_request() method requires fastmcp for full functionality.")
        print()
        return

    model = get_model(max_tokens=200)

    agent = Agent(
        model=model,
        tools=[get_weather, calculate],
        system_prompt="You are helpful.",
    )

    server = LocusMCPServer(agent=agent, name="test-server")

    # Simulate MCP tools/list request
    list_request = {"method": "tools/list", "params": {}}
    list_response = await server.handle_request(list_request)

    print("Request: tools/list")
    print(f"Response: {json.dumps(list_response, indent=2)[:500]}...")
    print()

    # Simulate MCP tools/call request
    call_request = {
        "method": "tools/call",
        "params": {
            "name": "get_weather",
            "arguments": {"city": "London"},
        },
    }
    call_response = await server.handle_request(call_request)

    print("Request: tools/call (get_weather)")
    print(f"Response: {json.dumps(call_response, indent=2)}")
    print()


# =============================================================================
# Part 5: MCP Client (Connecting to External Servers)
# =============================================================================


def example_mcp_client():
    """Connect to external MCP servers."""
    print("=== Part 5: MCP Client ===\n")

    print("MCPClient allows Locus agents to use tools from external MCP servers.")
    print()

    print("Example usage:")
    print("""
    # Connect to an MCP server
    client = MCPClient(server_command=["python", "weather_server.py"])
    await client.connect()

    # List available tools
    tools = await client.list_tools()
    print(f"Available tools: {tools}")

    # Call a tool
    result = await client.call_tool("get_weather", {"city": "Paris"})
    print(f"Result: {result}")

    # Convert MCP tools to Locus tools
    locus_tools = client.to_locus_tools(tools)

    # Use in a Locus agent
    agent = Agent(
        model=model,
        tools=locus_tools,  # Tools from the MCP server!
        system_prompt="Use the available tools.",
    )

    # Close connection
    await client.close()
    """)
    print()


# =============================================================================
# Part 6: Complete MCP Integration Example
# =============================================================================


async def example_complete_integration():
    """Complete example of MCP integration."""
    print("=== Part 6: Complete Integration ===\n")

    try:
        import fastmcp  # noqa: F401

        has_fastmcp = True
    except ImportError:
        has_fastmcp = False

    model = get_model(max_tokens=300)

    # Step 1: Create an agent with tools
    agent = Agent(
        model=model,
        tools=[get_weather, search_database, calculate],
        system_prompt="""You are a helpful assistant.
Use the available tools to answer questions:
- get_weather: Check weather in cities
- search_database: Search for information
- calculate: Do math calculations""",
    )

    # Step 2: Create MCP server
    server = create_mcp_server(agent, name="multi-tool-assistant")

    print(f"Created MCP server: {server.name}")
    print(f"Agent tools: {[t.name for t in [get_weather, search_database, calculate]]}")
    print()

    if not has_fastmcp:
        print("Note: fastmcp not installed - showing structure only.")
        print("Install with: pip install fastmcp")
        print()
        print("With fastmcp installed, the server can:")
        print("  - Handle tools/list requests")
        print("  - Handle tools/call requests")
        print("  - Run as stdio or SSE transport")
        print()
        return

    # Step 3: Test the server handles requests
    print("Testing MCP server with simulated requests:\n")

    # Test tools/list
    tools_response = await server.handle_request({"method": "tools/list"})
    tool_names = [t["name"] for t in tools_response.get("tools", [])]
    print(f"Available tools: {tool_names}")

    # Test run_agent (if model is not mock)
    if type(model).__name__ != "MockModel":
        run_response = await server.handle_request(
            {
                "method": "tools/call",
                "params": {
                    "name": "run_agent",
                    "arguments": {"prompt": "What's the weather in Tokyo?"},
                },
            }
        )
        print(f"\nAgent response: {run_response}")

    print()
    print("This server can now be used by any MCP-compatible client!")
    print()


# =============================================================================
# Part 7: MCP Best Practices
# =============================================================================


def example_best_practices():
    """Best practices for MCP integration."""
    print("=== Part 7: Best Practices ===\n")

    print("1. Tool Design")
    print("-" * 40)
    print("   - Use clear, descriptive tool names")
    print("   - Write detailed docstrings (they become descriptions)")
    print("   - Use type hints for parameters")
    print("   - Return strings or JSON-serializable data")
    print()

    print("2. Error Handling")
    print("-" * 40)
    print("   - Return error messages as strings, don't raise exceptions")
    print("   - Validate inputs before processing")
    print("   - Include helpful error messages")
    print()

    print("3. Security")
    print("-" * 40)
    print("   - Validate all inputs")
    print("   - Limit what tools can access")
    print("   - Use hooks for additional validation")
    print("   - Don't expose sensitive operations")
    print()

    print("4. Performance")
    print("-" * 40)
    print("   - Keep tools focused and fast")
    print("   - Use async for I/O operations")
    print("   - Consider caching for repeated calls")
    print()


# =============================================================================
# Main
# =============================================================================


async def main():
    """Run all tutorial parts."""
    print("=" * 60)
    print("Tutorial 12: MCP Integration")
    print("=" * 60)
    print()

    print_config()
    print()

    example_locus_tools()
    example_tool_conversion()
    example_mcp_server()
    await example_mcp_requests()
    example_mcp_client()
    await example_complete_integration()
    example_best_practices()

    print("=" * 60)
    print("Congratulations! You've completed the Locus tutorial series.")
    print("=" * 60)
    print()
    print("Summary of tutorials:")
    print("  01: Basic Agent")
    print("  02: Agent with Tools")
    print("  03: Agent Memory & Checkpointing")
    print("  04: Agent Streaming & Events")
    print("  05: Agent Hooks & Lifecycle")
    print("  06: Basic StateGraph")
    print("  07: Conditional Routing")
    print("  08: State Reducers")
    print("  09: Human-in-the-Loop")
    print("  10: Advanced Patterns")
    print("  11: Swarm Multi-Agent")
    print("  12: MCP Integration")
    print()
    print("Multi-modal/vision support is planned for a future release.")


if __name__ == "__main__":
    asyncio.run(main())
