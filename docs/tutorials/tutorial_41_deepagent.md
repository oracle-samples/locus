# Tutorial 41: DeepAgent — research-shaped agent factory

`create_deepagent` bundles the standard deep-research configuration into one
call: reflexion + grounding on by default, a typed termination algebra, and
optional capability layers (filesystem scratchspace, todo tracking, subagent
spawning) — all producing a plain `locus.Agent`.

Architecture::

    create_deepagent(model, tools, system_prompt, output_schema=…)
          │
          ▼
    Agent(
      reflexion=True, grounding=True,
      termination = (ToolCalled("submit") & ConfidenceMet(min_confidence))
                    | TokenLimit(max_tokens)
                    | MaxIterations(max_iterations),
      output_schema = <your Pydantic model>,
      …optional: filesystem tools, todo tools, task() subagent dispatcher…
    )

This tutorial covers:

1. A basic `create_deepagent` with a typed submit tool — the agent loops,
   self-corrects via reflexion, grounds claims against tool results, and
   submits a structured `ModuleReport`.
2. Filesystem-as-memory: enabling `write_file` / `read_file` scratchpad
   tools so the agent externalizes intermediate notes across long runs.
3. Todo tracking: `write_todos` / `read_todos` tools backed by a `TodoState`
   the caller can inspect after the run.
4. Subagent dispatch: defining a `SubAgentDef` and spawning it via `task()`
   for focused sub-investigation without bloating the parent's context.
5. Observability: `deepagent.*` SSE events — `subagent.spawned/completed`,
   `fs.read/write`, `todo.added/completed`.
6. `datastores=`: auto-wire named `search_<name>` tools from
   `RAGRetriever` instances so the agent can route queries to the
   right vector store. See [the deep-research project][dr] for full
   ports against Oracle Autonomous Database, OCI Object Storage, and
   OpenSearch.

[dr]: https://github.com/oracle-samples/locus/tree/main/examples/projects/deep-research

Why this is differentiated:

* The factory is a pure convenience layer — `create_deepagent` returns a
  standard `locus.Agent`. Every hook, plugin, checkpointer, and evaluation
  primitive from the rest of the SDK attaches normally.
* Typed termination is composable and testable: `(ToolCalled("submit") &
  ConfidenceMet(0.85)) | TokenLimit(80_000)` reads like a sentence and
  can be unit-tested without running a model.
* Subagents run as one-shot stateless calls — the parent's context window
  never sees the subagent's full trajectory, only its final answer.

Run::

    python examples/tutorial_41_deepagent.py

Difficulty: Intermediate
Prerequisites: tutorial_01_basic_agent (Agent),
tutorial_37_termination (typed termination)

## Source

```python
--8<-- "examples/tutorial_41_deepagent.py"
```
