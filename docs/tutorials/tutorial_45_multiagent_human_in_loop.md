# Tutorial 45: Multi-agent workflows with human-in-the-loop

Tutorial 09 covered HITL with a single agent. Real production agentic
systems rarely look like that — most of them have:

    1. A triage agent that classifies incoming work.
    2. Specialist agents that do the work.
    3. A *human approval gate* before any irreversible action.
    4. An *escalation path* when the agents can't decide.

This tutorial walks three patterns that combine multi-agent workflows
with human input. All three use the ``interrupt()`` primitive so the
graph **pauses, returns control to the caller, then resumes** when the
human responds — no busy-waiting, no callback hell.

Patterns covered:

* **Pattern A — Approval gate**: a Triage agent classifies a refund
  request, a Specialist drafts the response, a human approves before
  it ships.
* **Pattern B — Human-as-tool**: when the Triage agent isn't confident,
  it asks the human a structured question rather than guessing. The
  human's answer becomes part of state for downstream specialists.
* **Pattern C — Multi-step interrupt + checkpoint**: the graph saves
  state across an interrupt boundary so a human can come back hours
  later (different process / different caller) and the workflow
  picks up where it left off.

What's differentiated about Locus here:

* ``interrupt()`` is a function-level primitive — no need to wire a
  separate "wait-for-human" node type. Any node can pause.
* The graph executor returns an ``InterruptState`` that carries the
  full workflow state. Resume by calling ``graph.execute(Command(
  resume=...))``. State doesn't have to live in a global anywhere.
* Combine with a ``checkpointer`` and the workflow can pause for
  hours/days while preserving every specialist's context.
* Set ``LOCUS_MODEL_PROVIDER=oci|openai`` to drive real specialists.

Run::

    python examples/tutorial_45_multiagent_human_in_loop.py

Difficulty: Advanced
Prerequisites: tutorial_09_human_in_the_loop, tutorial_43 (this series)

## Source

```python
--8<-- "examples/tutorial_45_multiagent_human_in_loop.py"
```
