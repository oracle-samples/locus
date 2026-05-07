# Tutorial 51: Cognitive router — bounded graph generation

``locus.router`` is a meta-orchestration layer that compiles natural language
onto existing locus primitives. The LLM never picks topology — it fills a typed
``GoalFrame``; the router selects a protocol deterministically and the compiler
emits a real ``Agent`` / ``SequentialPipeline`` / ``ParallelPipeline`` /
``LoopAgent`` from a curated registry.

Pipeline::

    natural-language input
          │
          ▼
    Agent(output_schema=GoalFrame)     ← LLM fills typed schema only
          │ GoalFrame(primary_goal, domain, complexity, risk, …)
          ▼
    ProtocolRegistry.select(frame)     ← deterministic filter + ranking
          │ Protocol (e.g. "specialist_fanout")
          ▼
    PolicyGate.check(frame, protocol)  ← allow | require_approval | deny
          │
          ▼
    CognitiveCompiler.compile(…)       ← emits Runnable adapter
          │ wraps real Agent / Pipeline / Orchestrator
          ▼
    runnable.execute(task)
          │
          ▼
    RunnableResult(text, protocol_id, frame)

This tutorial covers:

1. Defining a small capability set (annotated tools).
2. Registering all 8 built-in protocols.
3. Loading ``SKILL.md`` packages and tagging them by domain so every
   emitted Agent gets the right catalog at runtime.
4. Standing up a ``Router`` with a ``GoalFrame`` extractor and a
   ``CognitiveCompiler``.
5. Dispatching five distinct inputs that hit five different protocols
   (``direct_response`` / ``plan_execute_validate`` / ``specialist_fanout`` /
   ``debate`` / ``codegen_test_validate``) and printing which protocol fired,
   the compiled runtime shape, and the result.

Why this is differentiated:

* The LLM never touches orchestration topology — it fills exactly one typed
  schema. Everything downstream (protocol selection, policy gating, compilation)
  is rule-based and reproducible.
* Eight built-in protocols cover the cardinal shapes: single-Agent,
  3-stage SequentialPipeline, ParallelPipeline fanout, debate + judge, PASS/FAIL
  LoopAgent, approval-gated execution, A2A delegation, one-tool handoff chain.
* Adding a domain (observability, codegen, support) is one ``CapabilityIndex``
  swap — no new protocol needed.

Run::

    python examples/tutorial_51_cognitive_router.py

Difficulty: Intermediate
Prerequisites: tutorial_01_basic_agent (Agent), tutorial_11_swarm_multiagent
(Orchestrator), tutorial_13_structured_output (structured output)

## Source

```python
--8<-- "examples/tutorial_51_cognitive_router.py"
```
