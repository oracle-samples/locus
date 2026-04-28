# Orchestrator + Specialists

One coordinator picks which specialist handles each sub-task. The
specialists never talk to each other — only to the orchestrator. Think
project manager + team.

```python
from locus.multiagent import Orchestrator, Specialist

researcher = Specialist(name="researcher", agent=research_agent,
                        description="Reads the catalogue and quotes vendors.")
compliance = Specialist(name="compliance", agent=compliance_agent,
                        description="Vets vendors against SOC2/ISO posture.")

orchestrator = Orchestrator(
    coordinator_model="oci:openai.gpt-5.5",
    specialists=[researcher, compliance],
    system_prompt="You're the procurement lead. Delegate to specialists.",
)

result = orchestrator.run_sync("Pick three vendors for $2M of cloud spend.")
```

The coordinator is a regular agent whose tool-set is *the specialists*.
Calling a specialist runs that specialist's full agent loop and returns
the answer. Specialists run in parallel when the coordinator dispatches
to multiple of them in one turn.

## Why this shape

- **Clarity of cost.** You see exactly which specialist ran on each
  sub-task — useful when a single specialist is the bottleneck.
- **Confidence floors.** A specialist can decline (`confidence < 0.6`),
  forcing the coordinator to try someone else.
- **Token economics.** Specialists carry their own short system
  prompts; the coordinator stays small.

## When to use

- The work splits cleanly into expert domains.
- You want one place to attribute decisions to (the coordinator).
- Specialists need their own playbooks or skills.

## Tutorial

[`tutorial_17_orchestrator_pattern.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_17_orchestrator_pattern.py)
shows a router + three specialists running in parallel and merging
their outputs. See also
[`tutorial_18_specialist_agents.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_18_specialist_agents.py)
for confidence floors and playbooks.

## Source

`src/locus/multiagent/orchestrator.py`.
