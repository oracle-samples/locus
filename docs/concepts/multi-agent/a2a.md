# Agent-to-Agent (A2A) protocol

A2A is the cross-process / cross-runtime version of multi-agent. Each
agent runs as its own service, advertises an `AgentCard` (capabilities

+ contact info), and other agents discover and call it over HTTP.

```python
from locus.a2a.protocol import A2AServer, A2AClient, AgentCard

# host side: expose an agent over A2A
card = AgentCard(
    name="vendor_research",
    description="Reads the vendor catalogue, quotes prices.",
    skills=["vendor_lookup", "price_quote"],
)
server = A2AServer(agent=research_agent, card=card)
server.run(port=7421)

# client side: discover and call
client = A2AClient.discover("http://research-host:7421")
reply = await client.send("Quote three options for $2M cloud.")
```

The protocol is HTTP + SSE. Discovery uses the `AgentCard` so a router
can pick agents by capability tag. Auth and TLS are standard HTTP
concerns.

## Why this shape

+ **Cross-team agents.** Different teams own different agents on
  different stacks; A2A lets them call each other without sharing
  process memory.
+ **Polyglot.** A locus agent can call a non-locus A2A peer if the
  peer speaks the same protocol.
+ **Failure isolation.** A peer crashes; the caller sees a timeout, not
  a crash.

## When to use

+ Multi-process or multi-host agent deployments.
+ You need a network boundary for security or scaling reasons.
+ You want capability-based discovery (`skills` tags).

## When not to use

+ Single-process — use one of the in-process patterns instead.
+ Tight latency requirements where HTTP round-trips hurt.

## Tutorial

[`tutorial_34_a2a_protocol.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_34_a2a_protocol.py).

## Source

`src/locus/a2a/` — server, client, card, registry.
