# MCP (both ways)

The [Model Context Protocol](https://modelcontextprotocol.io) is an
Anthropic-spec interop standard for tools. locus speaks MCP in both
directions.

## Consume MCP servers

`MCPClient` wraps an external MCP server's tools so the agent can call
them as if they were native locus tools.

```python
from locus.integrations.fastmcp import MCPClient

# spawn the MCP server as a subprocess (stdio transport)
fs = MCPClient.stdio(command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/data"])

agent = Agent(model=..., tools=[*fs.tools()])  # MCP tools become locus tools
```

The client registers every MCP tool with locus's tool registry, with
schema, descriptions, and call-through plumbing intact.

## Expose locus tools as MCP

`LocusMCPServer` turns a set of locus tools into an MCP server other
agents can consume.

```python
from locus.integrations.fastmcp import LocusMCPServer

server = LocusMCPServer(tools=[search_vendors, submit_po])
server.run_stdio()        # or .run_http(port=7400)
```

Anthropic Claude, Strands, or any MCP-spec client can now call your
locus tools.

## Round-trip example

A common shape: locus agent A consumes an MCP filesystem server, plus
a locus agent B exposed as MCP that A can also call. Same client API,
different transports.

## Tutorial

[`tutorial_12_mcp_integration.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_12_mcp_integration.py).

## Source

`src/locus/integrations/mcp/` — built on FastMCP.
