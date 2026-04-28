# Handoff

Handoff is what an escalation desk does. One agent owns the
conversation, decides it needs a different role, and hands the *whole*
transcript to the next agent — who picks up where it left off.

```python
from locus.multiagent import Handoff

triage   = Agent(model=..., system_prompt="You triage tickets.")
billing  = Agent(model=..., system_prompt="You handle billing escalations.")
shipping = Agent(model=..., system_prompt="You handle shipping issues.")

flow = Handoff(
    initial=triage,
    targets={"billing": billing, "shipping": shipping},
)

result = flow.run_sync("My order #4321 was charged twice.")
```

The triage agent ends a turn with a `Handoff(target="billing")`
directive. The full message history transfers; the billing agent reads
it as if it were the next turn of the same conversation. State,
checkpointer, and `thread_id` survive.

## When to use

- Customer-support flows where the *conversation* is the unit of work.
- "Pass to a human" — the human simply replaces one of the targets.
- Escalation when the first agent realises it's the wrong specialist.

## Difference from Orchestrator

- **Orchestrator**: coordinator delegates a *sub-task* and waits for
  the answer; the conversation belongs to the coordinator.
- **Handoff**: the conversation itself moves; the previous owner is
  out of the loop.

## Tutorial

[`tutorial_16_agent_handoff.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_16_agent_handoff.py).

## Source

`src/locus/multiagent/handoff.py`.
