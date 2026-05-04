# Tutorial 42: Map-Reduce code-review crew

This tutorial covers a multi-agent pattern that's awkward in most
SDKs but native in Locus: **scatter-gather** via the ``Send`` primitive.

The setup:
    Diff splitter      ──>  N Reviewers (parallel)  ──>  Synthesizer
   (one node, fan-out)        (run in parallel via Send)     (one node, reduce)

What's differentiated about Locus here:

- ``Send`` is a first-class graph primitive — the splitter just returns a
  list of ``Send(...)``s and the executor spawns parallel reviewers.
- The synthesizer reads each reviewer's output by name from the merged
  state. No queues, no manual ``asyncio.gather``, no shared mutable state.
- Each reviewer is a separate Locus ``Agent`` with its own role, system
  prompt, and tool set. The graph orchestrates them, not a hand-written
  for-loop.
- Whole pipeline is one ``StateGraph.execute`` call. Streaming, cancel,
  checkpoint, GSAR judgment all attach for free.

Run::

    python examples/tutorial_42_map_reduce_code_review.py

Difficulty: Advanced
Prerequisites: tutorial_06_basic_graph, tutorial_11_swarm_multiagent

## Source

```python
--8<-- "examples/tutorial_42_map_reduce_code_review.py"
```
